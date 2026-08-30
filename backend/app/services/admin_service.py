"""运营看板 + 审核管理（阶段 7，文档⑲数据统计与看板管理）+ 用户封禁/解封。

stats：实时聚合（课设规模直接 COUNT，不建 daily_stats 汇总表）。
reviews：转人工复审的记录由系统管理员处理（POST /admin/reviews/{id}/handle）。
"""
from datetime import datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.response import NotFoundError, ParamError
from app.models.comment import Comment
from app.models.community import Community
from app.models.like import CommentLike, PostLike
from app.models.post import Post, POST_STATUS_BANNED
from app.models.review import CONTENT_POST, REVIEW_MANUAL, REVIEW_PASSED, REVIEW_REJECTED, Review
from app.models.user import User
from app.services.notify_service import notify


def set_user_status(db: Session, user_id: int, status: int) -> User:
    """封禁(1)/解封(0)/注销(2) 用户：系统管理员操作，写通知。"""
    if status not in (0, 1, 2):
        raise ParamError("status 仅支持 0正常 1封禁 2注销")
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("用户不存在")
    if user.user_type == 1:
        raise ParamError("不能操作系统管理员账号")
    user.status = status
    db.commit()
    db.refresh(user)
    if status == 1:
        notify(db, user.id, "system", "你的账号已被封禁", summary="如有疑问请联系平台管理员")
    elif status == 0:
        notify(db, user.id, "system", "你的账号已解封", summary="欢迎回来")
    return user


def overview_stats(db: Session) -> dict:
    """全局运营看板数据。"""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = datetime.now() - timedelta(days=7)

    def count(model, *conds) -> int:
        stmt = select(func.count(model.id))
        if conds:
            stmt = stmt.where(*conds)
        return db.execute(stmt).scalar_one()

    users_total = count(User)
    communities_total = count(Community)
    posts_total = count(Post, Post.status == 0)
    comments_total = count(Comment, Comment.status == 0)
    likes_total = count(PostLike) + count(CommentLike)  # 08-29 拆表：两表求和

    # 近 7 天发帖趋势
    rows = db.execute(
        text(
            "SELECT DATE(created_at) AS d, COUNT(*) AS cnt FROM posts "
            "WHERE created_at >= :since GROUP BY DATE(created_at) ORDER BY d"
        ),
        {"since": week_ago},
    ).all()
    trend = [{"date": str(r[0]), "count": r[1]} for r in rows]

    # 帖子最多的 Top5 频道
    top = db.execute(
        select(Post.community_id, func.count(Post.id).label("cnt"))
        .where(Post.status == 0)
        .group_by(Post.community_id)
        .order_by(text("cnt DESC"))
        .limit(5)
    ).all()
    communities = {
        c.id: c.name
        for c in db.execute(select(Community).where(Community.id.in_([t[0] for t in top]))).scalars().all()
    } if top else {}
    top_communities = [
        {"community_id": cid, "name": communities.get(cid, f"#{cid}"), "posts": cnt}
        for cid, cnt in top
    ]

    return {
        "users_total": users_total,
        "communities_total": communities_total,
        "posts_total": posts_total,
        "comments_total": comments_total,
        "likes_total": likes_total,
        "users_today": count(User, User.created_at >= today_start),
        "posts_today": count(Post, Post.status == 0, Post.created_at >= today_start),
        "posts_trend_7d": trend,
        "top_communities": top_communities,
    }


def list_reviews(db: Session, status: int | None, page: int, page_size: int) -> dict:
    """审核记录分页（可选按状态过滤）。"""
    stmt = select(Review).order_by(Review.id.desc())
    count_stmt = select(func.count(Review.id))
    if status is not None:
        stmt = stmt.where(Review.status == status)
        count_stmt = count_stmt.where(Review.status == status)
    total = db.execute(count_stmt).scalar_one()
    items = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    # 批量预取关联帖子标题，避免每行一次 db.get（N+1）
    post_ids = {r.content_id for r in items if r.content_type == CONTENT_POST}
    titles = (
        {
            p.id: p.title
            for p in db.execute(select(Post).where(Post.id.in_(post_ids))).scalars().all()
        }
        if post_ids else {}
    )
    return {
        "items": [_out(r, titles) for r in items],
        "total": total, "page": page, "page_size": page_size,
    }


def handle_review(db: Session, reviewer: User, review_id: int, approve: bool) -> Review:
    """系统管理员人工处理转人工复审的审核记录。"""
    review = db.get(Review, review_id)
    if review is None:
        raise NotFoundError("审核记录不存在")
    if review.status != REVIEW_MANUAL:
        raise ParamError("仅可处理转人工复审的记录")

    review.reviewer_id = reviewer.id
    review.review_method = 2  # 人工审核
    review.reviewed_at = datetime.now()
    post = db.get(Post, review.content_id) if review.content_type == CONTENT_POST else None

    if approve:
        review.status = REVIEW_PASSED
        # 仅恢复因违规下架的帖子（BANNED）；作者主动删除（DELETED）的不复活
        if post is not None and post.status == POST_STATUS_BANNED:
            post.status = 0
        review.result = "人工审核通过，帖子已恢复"
        notify(
            db, review.user_id, "system", "你的帖子已通过人工复审",
            summary="内容已恢复可见", ref_id=review.content_id, community_id=post.community_id if post else None,
        )
    else:
        review.status = REVIEW_REJECTED
        review.result = "人工审核维持驳回"
        notify(
            db, review.user_id, "system", "你的帖子经人工复审仍被驳回",
            summary="内容维持下架", ref_id=review.content_id, community_id=post.community_id if post else None,
        )
    db.commit()
    db.refresh(review)
    return review


def _out(r: Review, titles: dict) -> dict:
    from app.api.v1.ai import _review_out

    out = _review_out(r)
    out["post_title"] = titles.get(r.content_id, "") if r.content_type == CONTENT_POST else ""
    return out
