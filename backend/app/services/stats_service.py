"""运营数据统计（文档⑲数据统计与看板管理，P0）。

- compute_daily_stats：按日聚合写入 daily_stats（新增/活跃成员、发帖、互动、违规、AI 调用、留存率）
- dashboard_trend：近 N 天趋势（看板）
- export_stats：报表导出 CSV
- 活跃定义：当日发帖/评论/点赞/关注/收藏的独立用户
- 留存率：当日活跃且前一日也活跃的用户占比（近似日留存）
"""
import csv
import io
from datetime import date, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.ai_call_log import AiCallLog
from app.models.comment import Comment
from app.models.daily_stat import DailyStat
from app.models.favorite import Favorite
from app.models.follow import Follow
from app.models.like import CommentLike, PostLike
from app.models.post import Post
from app.models.review import REVIEW_REJECTED, Review
from app.models.user import User


def _day_range(d: date) -> tuple[datetime, datetime]:
    start = datetime(d.year, d.month, d.day)
    return start, start + timedelta(days=1)


def _active_user_ids(db: Session, d: date) -> set[int]:
    """当日活跃用户（发帖/评论/点赞/关注/收藏）。"""
    start, end = _day_range(d)
    ids: set[int] = set()
    for model, col in (
        (Post, Post.author_id),
        (Comment, Comment.author_id),
        (PostLike, PostLike.user_id),
        (CommentLike, CommentLike.user_id),
        (Follow, Follow.user_id),
        (Favorite, Favorite.user_id),
    ):
        rows = db.execute(
            select(col).where(model.created_at >= start, model.created_at < end)
        ).scalars().all()
        ids.update(rows)
    return ids


def compute_daily_stats(db: Session, d: date | None = None) -> DailyStat:
    """计算并 upsert 某日统计（默认今天）。"""
    d = d or date.today()
    start, end = _day_range(d)

    new_members = db.execute(
        select(func.count(User.id)).where(User.created_at >= start, User.created_at < end)
    ).scalar_one()
    posts = db.execute(
        select(func.count(Post.id)).where(Post.created_at >= start, Post.created_at < end)
    ).scalar_one()
    comments = db.execute(
        select(func.count(Comment.id)).where(Comment.created_at >= start, Comment.created_at < end)
    ).scalar_one()
    likes = (
        db.execute(select(func.count(PostLike.id)).where(PostLike.created_at >= start, PostLike.created_at < end)).scalar_one()
        + db.execute(select(func.count(CommentLike.id)).where(CommentLike.created_at >= start, CommentLike.created_at < end)).scalar_one()
    )
    follows = db.execute(
        select(func.count(Follow.id)).where(Follow.created_at >= start, Follow.created_at < end)
    ).scalar_one()
    favorites = db.execute(
        select(func.count(Favorite.id)).where(Favorite.created_at >= start, Favorite.created_at < end)
    ).scalar_one()
    violations = db.execute(
        select(func.count(Review.id)).where(
            Review.created_at >= start, Review.created_at < end, Review.status == REVIEW_REJECTED
        )
    ).scalar_one()
    ai_calls = db.execute(
        select(func.count(AiCallLog.id)).where(AiCallLog.created_at >= start, AiCallLog.created_at < end)
    ).scalar_one()

    active = _active_user_ids(db, d)
    retention = 0
    if active:
        prev_active = _active_user_ids(db, d - timedelta(days=1))
        overlap = len(active & prev_active)
        retention = round(overlap * 100 / len(active))

    row = db.execute(select(DailyStat).where(DailyStat.stat_date == d)).scalar_one_or_none()
    if row is None:
        row = DailyStat(stat_date=d)
        db.add(row)
    row.new_members = new_members
    row.active_members = len(active)
    row.posts = posts
    row.interactions = comments + likes + follows + favorites
    row.violations = violations
    row.ai_calls = ai_calls
    row.retention = retention
    db.commit()
    db.refresh(row)
    return row


def dashboard_trend(db: Session, days: int = 7) -> dict:
    """近 N 天趋势：读 daily_stats。

    - 今日缺行：实时补齐计算（数据新鲜）；
    - 历史缺行：填零空值，避免对多天做全表聚合重扫（后台统计任务会逐步回填）。
    """
    today = date.today()
    stats = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        row = db.execute(select(DailyStat).where(DailyStat.stat_date == d)).scalar_one_or_none()
        if row is None:
            if d == today:
                row = compute_daily_stats(db, d)
            else:
                stats.append(_empty_out(d))
                continue
        stats.append(_out(row))
    # 汇总近 N 天
    summary = {
        "new_members": sum(s["new_members"] for s in stats),
        "active_members": sum(s["active_members"] for s in stats),
        "posts": sum(s["posts"] for s in stats),
        "interactions": sum(s["interactions"] for s in stats),
        "violations": sum(s["violations"] for s in stats),
        "ai_calls": sum(s["ai_calls"] for s in stats),
    }
    # 数据一致性探针：v_community_overview 对比缓存计数与源表实数，
    # 不一致即存在漂移（对账口径，支撑 sp_reconcile_counters 的必要性）
    return {"days": days, "items": stats, "summary": summary, "reconcile": _overview_drift(db)}


def _overview_drift(db: Session) -> dict:
    """v_community_overview 一致性探针：返回漂移频道数（视图缺失时 -1）。"""
    try:
        drift = db.execute(text(
            "SELECT COUNT(*) FROM v_community_overview "
            "WHERE member_count <> actual_members OR post_count <> actual_posts"
        )).scalar_one()
        total = db.execute(text("SELECT COUNT(*) FROM v_community_overview")).scalar_one()
        return {"community_total": total, "community_drift": drift}
    except Exception:
        # 视图未创建（如测试库 create_all）→ 无法校验，标记为未知
        return {"community_total": -1, "community_drift": -1}


def export_stats(db: Session, days: int = 7) -> str:
    """导出统计报表 CSV（BOM 兼容 Excel）。"""
    trend = dashboard_trend(db, days)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["日期", "新增成员", "活跃成员", "发帖量", "互动总量", "违规数", "AI 调用", "留存率%"])
    for s in trend["items"]:
        writer.writerow([
            s["stat_date"], s["new_members"], s["active_members"], s["posts"],
            s["interactions"], s["violations"], s["ai_calls"], s["retention"],
        ])
    writer.writerow([])
    writer.writerow(["汇总", *[trend["summary"][k] for k in ("new_members", "active_members", "posts", "interactions", "violations", "ai_calls")]])
    return buf.getvalue()


def _out(s: DailyStat) -> dict:
    return {
        "stat_date": s.stat_date.isoformat(),
        "new_members": s.new_members,
        "active_members": s.active_members,
        "posts": s.posts,
        "interactions": s.interactions,
        "violations": s.violations,
        "ai_calls": s.ai_calls,
        "retention": s.retention,
    }


def _empty_out(d: date) -> dict:
    """历史缺行：零值占位。"""
    return {
        "stat_date": d.isoformat(),
        "new_members": 0,
        "active_members": 0,
        "posts": 0,
        "interactions": 0,
        "violations": 0,
        "ai_calls": 0,
        "retention": 0,
    }
