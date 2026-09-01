"""频道运营中心（频道主专属）：昨日数据 / 用户数据 / 内容分析 / 多维排名。

数据源：
- members（现存成员 + join_time → 新增/累计）
- community_event_logs（join/leave/visit 事件 → 退出成员数、访问人数次数）
- posts / comments / post_likes / comment_likes / reviews（内容与互动时序）
- post.view_count（帖子浏览量）
- boards（按板块分组）

说明：
- 退出成员数、访问人数次数依赖 community_event_logs 从上线起累计；历史存量（迁移前）无法回填，
  视为 0 / 缺失（前端标注"统计自日志上线起"）。
- 昨日口径：昨天 00:00~23:59:59；历史更早日期暂不回溯（课设规模，聚焦"昨日"与"今日"对比）。
"""
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import get_member_perms
from app.models.board import Board
from app.models.comment import Comment
from app.models.community import Community
from app.models.community_event_log import CommunityEventLog, EVENT_JOIN, EVENT_LEAVE, EVENT_VISIT
from app.models.like import PostLike
from app.models.member import Member
from app.models.post import Post

# 权限点：成员数据（运营中心核心数据）可见所需权限
PERM_OPS_VISIBLE = {"member_manage", "moderate"}


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    return datetime.combine(d, time.min), datetime.combine(d, time.max) + timedelta(microseconds=1)


def _count(db: Session, model, *conds) -> int:
    stmt = select(func.count(model.id))
    if conds:
        stmt = stmt.where(*conds)
    return db.execute(stmt).scalar_one()


def _distinct(db: Session, model, col, *conds) -> int:
    stmt = select(func.count(func.distinct(col)))
    if conds:
        stmt = stmt.where(*conds)
    return db.execute(stmt).scalar_one()


def _event_count(db: Session, community_id: int, event: str, start: datetime, end: datetime) -> int:
    return _count(
        db, CommunityEventLog,
        CommunityEventLog.community_id == community_id,
        CommunityEventLog.event == event,
        CommunityEventLog.created_at >= start,
        CommunityEventLog.created_at < end,
    )


def _sum(db: Session, model, col, *conds) -> int:
    stmt = select(func.coalesce(func.sum(col), 0))
    if conds:
        stmt = stmt.where(*conds)
    return db.execute(stmt).scalar_one()


def _event_distinct_users(db: Session, community_id: int, event: str, start: datetime, end: datetime) -> int:
    return _distinct(
        db, CommunityEventLog, CommunityEventLog.user_id,
        CommunityEventLog.community_id == community_id,
        CommunityEventLog.event == event,
        CommunityEventLog.created_at >= start,
        CommunityEventLog.created_at < end,
    )


def log_event(db: Session, community_id: int, user_id: int | None, event: str) -> None:
    """写一条频道事件日志（join/leave/visit）。访客 visit 时 user_id 可为 None。"""
    db.add(CommunityEventLog(community_id=community_id, user_id=user_id, event=event))
    db.flush()


def can_view_ops(db: Session, community: Community, user) -> bool:
    """运营中心可见：频道主 或 拥有成员管理/内容管理权限 或 平台管理员。"""
    if user.user_type == 1:
        return True
    if community.owner_id == user.id:
        return True
    perms = get_member_perms(db, community.id, user)
    return bool(perms & PERM_OPS_VISIBLE)


def _board_map(db: Session, community_id: int) -> dict[int, str]:
    rows = db.execute(
        select(Board).where(Board.community_id == community_id, Board.status == 0).order_by(Board.sort, Board.id)
    ).scalars().all()
    return {b.id: b.name for b in rows}


def _post_rank(db: Session, community_id: int, board_id: int | None, start: datetime, end: datetime) -> list[dict]:
    """帖子排名：周期内新增帖子的活跃度（赞×1+评×2+藏×3）降序 Top10。"""
    stmt = (
        select(Post)
        .where(Post.community_id == community_id, Post.status == 0,
               Post.created_at >= start, Post.created_at < end)
        .order_by((Post.like_count + 2 * Post.comment_count + 3 * Post.favorite_count).desc(), Post.view_count.desc(), Post.id.desc())
        .limit(10)
    )
    if board_id:
        stmt = stmt.where(Post.board_id == board_id)
    posts = db.execute(stmt).scalars().all()
    return [
        {
            "id": p.id, "title": p.title, "board_id": p.board_id,
            "view_count": p.view_count, "like_count": p.like_count,
            "comment_count": p.comment_count, "favorite_count": p.favorite_count,
            "heat": p.like_count + 2 * p.comment_count + 3 * p.favorite_count,
            "created_at": str(p.created_at),
        }
        for p in posts
    ]


def _member_rank(db: Session, community_id: int) -> list[dict]:
    """成员多维排名：发帖数 / 评论数 / 等级（按活跃度 = 发帖 + 评论 取 Top10）。"""
    post_cnt = dict(
        db.execute(
            select(Post.author_id, func.count(Post.id)).where(
                Post.community_id == community_id, Post.status == 0
            ).group_by(Post.author_id)
        ).all()
    )
    # 评论数：按评论作者分组（本频道帖子下的评论），过滤已删除评论
    comment_cnt = dict(
        db.execute(
            select(Comment.author_id, func.count(Comment.id))
            .join(Post, Post.id == Comment.post_id)
            .where(Post.community_id == community_id, Post.status == 0, Comment.status == 0)
            .group_by(Comment.author_id)
        ).all()
    )
    members = db.execute(
        select(Member).where(
            Member.community_id == community_id, Member.is_blocked.is_(False)
        ).order_by(Member.id.desc())
    ).scalars().all()
    rows = []
    for m in members:
        rows.append({
            "user_id": m.user_id, "nickname": m.nickname, "level": m.level,
            "member_type": m.member_type,
            "posts": post_cnt.get(m.user_id, 0),
            "comments": comment_cnt.get(m.user_id, 0),
        })
    rows.sort(key=lambda r: -(r["posts"] + r["comments"]))
    return rows[:10]


def ops_center(db: Session, community: Community, board_id: int | None = None) -> dict:
    """频道运营中心完整数据（须先经 can_view_ops 校验权限）。

    结构：
    - yesterday：昨日数据（含今日对比）
    - user：用户数据（成员数/帖子数累计；其余按 昨日/7天/30天 周期）
    - content：内容数据（帖子/浏览量/赞/评论 + 帖子排名，按 昨日/7天/30天 周期）
    """
    today = date.today()
    yesterday = today - timedelta(days=1)
    ys, ye = _day_bounds(yesterday)
    ts, te = _day_bounds(today)

    board_map = _board_map(db, community.id)
    bid = board_id if board_id in board_map or board_id is None else None
    board_filter = [Post.board_id == bid] if bid else []

    # ---------- 昨日数据（含今日对比） ----------
    yesterday_data = {
        "new_members": _event_count(db, community.id, EVENT_JOIN, ys, ye),
        "left_members": _event_count(db, community.id, EVENT_LEAVE, ys, ye),
        "visits": _count(
            db, CommunityEventLog, CommunityEventLog.community_id == community.id,
            CommunityEventLog.event == EVENT_VISIT, CommunityEventLog.created_at >= ys,
            CommunityEventLog.created_at < ye,
        ),
        "visitors": _event_distinct_users(db, community.id, EVENT_VISIT, ys, ye),
        "posts": _count(db, Post, Post.community_id == community.id, Post.status == 0,
                        Post.created_at >= ys, Post.created_at < ye, *board_filter),
        # 昨日浏览量：昨日新增帖子的 view_count 之和（当日真实值，非累计）
        "views": _sum(db, Post, Post.view_count,
                      Post.community_id == community.id, Post.status == 0,
                      Post.created_at >= ys, Post.created_at < ye, *board_filter),
        "post_authors": _distinct(db, Post, Post.author_id, Post.community_id == community.id,
                                  Post.status == 0, Post.created_at >= ys, Post.created_at < ye, *board_filter),
        "new_likes": _count(
            db, PostLike, PostLike.created_at >= ys, PostLike.created_at < ye,
            PostLike.post_id.in_(
                select(Post.id).where(Post.community_id == community.id, Post.status == 0)
            ),
        ),
        "new_comments": _count(
            db, Comment, Comment.status == 0, Comment.created_at >= ys, Comment.created_at < ye,
            Comment.post_id.in_(
                select(Post.id).where(Post.community_id == community.id, Post.status == 0)
            ),
        ),
    }

    # 今日（对比参考）
    today_data = {
        "new_members": _event_count(db, community.id, EVENT_JOIN, ts, te),
        "visits": _count(
            db, CommunityEventLog, CommunityEventLog.community_id == community.id,
            CommunityEventLog.event == EVENT_VISIT, CommunityEventLog.created_at >= ts,
            CommunityEventLog.created_at < te,
        ),
        "posts": _count(db, Post, Post.community_id == community.id, Post.status == 0,
                        Post.created_at >= ts, Post.created_at < te, *board_filter),
    }

    # ---------- 用户数据：累计只统计成员数+帖子数，其余按周期 ----------
    total_members = _count(db, Member, Member.community_id == community.id, Member.is_blocked.is_(False))
    total_posts = _count(db, Post, Post.community_id == community.id, Post.status == 0, *board_filter)

    # 按周期聚合（昨日 / 近7天 / 近30天），7/30 带每日序列
    def _user_period(days: int) -> dict:
        if days == 1:
            start, end = ys, ye
        else:
            start_d = today - timedelta(days=days - 1)
            start, _ = _day_bounds(start_d)
            end = te  # 覆盖到今天结束
        new_members = _event_count(db, community.id, EVENT_JOIN, start, end)
        visits = _count(
            db, CommunityEventLog, CommunityEventLog.community_id == community.id,
            CommunityEventLog.event == EVENT_VISIT,
            CommunityEventLog.created_at >= start, CommunityEventLog.created_at < end,
        )
        visitors = _event_distinct_users(db, community.id, EVENT_VISIT, start, end)
        active = len(set(_active_user_ids(db, community.id, start, end)))
        return {
            "new_members": new_members,
            "visits": visits,
            "visitors": visitors,
            "active_members": active,
            "active_rate": round(active * 100 / total_members, 1) if total_members else 0,
        }

    # 近 N 天每日序列（用户维度：新增成员/访问/访问人数/活跃）
    def _user_series(days: int) -> dict:
        start_d = today - timedelta(days=days - 1)
        dates: list[str] = []
        new_members: list[int] = []
        visits: list[int] = []
        visitors: list[int] = []
        active: list[int] = []
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            s, e = _day_bounds(d)
            dates.append(d.isoformat())
            new_members.append(_event_count(db, community.id, EVENT_JOIN, s, e))
            visits.append(_count(
                db, CommunityEventLog, CommunityEventLog.community_id == community.id,
                CommunityEventLog.event == EVENT_VISIT,
                CommunityEventLog.created_at >= s, CommunityEventLog.created_at < e,
            ))
            visitors.append(_event_distinct_users(db, community.id, EVENT_VISIT, s, e))
            active.append(len(set(_active_user_ids(db, community.id, s, e))))
        return {"dates": dates, "new_members": new_members, "visits": visits,
                "visitors": visitors, "active_members": active}

    # 近 N 天每日序列（内容维度：帖子/浏览量/赞/评论）
    def _content_series(days: int) -> dict:
        start_d = today - timedelta(days=days - 1)
        dates: list[str] = []
        posts: list[int] = []
        views: list[int] = []
        likes: list[int] = []
        comments: list[int] = []
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            s, e = _day_bounds(d)
            dates.append(d.isoformat())
            posts.append(_count(db, Post, Post.community_id == community.id, Post.status == 0,
                                Post.created_at >= s, Post.created_at < e, *board_filter))
            views.append(_sum(db, Post, Post.view_count,
                              Post.community_id == community.id, Post.status == 0,
                              Post.created_at >= s, Post.created_at < e, *board_filter))
            likes.append(_count(
                db, PostLike, PostLike.created_at >= s, PostLike.created_at < e,
                PostLike.post_id.in_(
                    select(Post.id).where(Post.community_id == community.id, Post.status == 0)
                ),
            ))
            comments.append(_count(
                db, Comment, Comment.status == 0, Comment.created_at >= s, Comment.created_at < e,
                Comment.post_id.in_(
                    select(Post.id).where(Post.community_id == community.id, Post.status == 0)
                ),
            ))
        return {"dates": dates, "posts": posts, "views": views, "likes": likes, "comments": comments}

    def _content_period(days: int) -> dict:
        if days == 1:
            start, end = ys, ye
        else:
            start_d = today - timedelta(days=days - 1)
            start, _ = _day_bounds(start_d)
            end = te  # 覆盖到今天结束
        return {
            "posts": _count(db, Post, Post.community_id == community.id, Post.status == 0,
                            Post.created_at >= start, Post.created_at < end, *board_filter),
            "views": _sum(db, Post, Post.view_count,
                          Post.community_id == community.id, Post.status == 0,
                          Post.created_at >= start, Post.created_at < end, *board_filter),
            "likes": _count(
                db, PostLike, PostLike.created_at >= start, PostLike.created_at < end,
                PostLike.post_id.in_(
                    select(Post.id).where(Post.community_id == community.id, Post.status == 0)
                ),
            ),
            "comments": _count(
                db, Comment, Comment.status == 0, Comment.created_at >= start, Comment.created_at < end,
                Comment.post_id.in_(
                    select(Post.id).where(Post.community_id == community.id, Post.status == 0)
                ),
            ),
            "post_rank": _post_rank(db, community.id, bid, start, end),
        }

    user_data = {
        "total_members": total_members,
        "total_posts": total_posts,
        "member_rank": _member_rank(db, community.id),
        "yesterday": _user_period(1),
        "d7": {**_user_period(7), "series": _user_series(7)},
        "d30": {**_user_period(30), "series": _user_series(30)},
    }

    content_data = {
        "yesterday": _content_period(1),
        "d7": {**_content_period(7), "series": _content_series(7)},
        "d30": {**_content_period(30), "series": _content_series(30)},
        "boards": [
            {
                "board_id": b[0], "board_name": b[1],
                "yesterday_posts": _count(
                    db, Post, Post.community_id == community.id, Post.board_id == b[0],
                    Post.status == 0, Post.created_at >= ys, Post.created_at < ye,
                ),
                "views": _sum(
                    db, Post, Post.view_count,
                    Post.community_id == community.id, Post.board_id == b[0], Post.status == 0,
                ),
                "deleted_posts": _count(
                    db, Post, Post.community_id == community.id, Post.board_id == b[0],
                    Post.status == 1, Post.created_at >= ys, Post.created_at < ye,
                ),
            }
            for b in board_map.items()
        ],
    }

    return {
        "yesterday": yesterday_data,
        "today": today_data,
        "user": user_data,
        "content": content_data,
        "date": yesterday.isoformat(),
        "note": "新增成员/退出成员/访问数据统计自日志上线起，历史存量不追溯",
    }


def _active_user_ids(db: Session, community_id: int, start: datetime, end: datetime) -> set[int]:
    """当日频道活跃用户（发帖/评论/点赞）。"""
    ids: set[int] = set()
    ids.update(
        db.execute(select(Post.author_id).where(
            Post.community_id == community_id, Post.status == 0,
            Post.created_at >= start, Post.created_at < end,
        )).scalars().all()
    )
    ids.update(
        db.execute(
            select(Comment.author_id)
            .join(Post, Post.id == Comment.post_id)
            .where(Post.community_id == community_id, Post.status == 0,
                   Comment.status == 0,
                   Comment.created_at >= start, Comment.created_at < end)
        ).scalars().all()
    )
    ids.update(
        db.execute(
            select(PostLike.user_id)
            .join(Post, Post.id == PostLike.post_id)
            .where(Post.community_id == community_id, Post.status == 0,
                   PostLike.created_at >= start, PostLike.created_at < end)
        ).scalars().all()
    )
    return ids