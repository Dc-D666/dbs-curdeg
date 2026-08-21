"""用户互关业务（文档⑨"关注目标类型（用户/频道）"用户侧，P0）。

幂等：(user_id, target_user_id) 唯一约束 + 先查后插 + IntegrityError 兜底；
关注成功后通知被关注者（新粉丝，走 events.EVENT_FOLLOW 开关）。
"""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.response import NotFoundError
from app.models.user import User
from app.models.user_follow import UserFollow
from app.services.notify_service import notify


def follow_user(db: Session, user: User, target_user_id: int) -> dict:
    """关注用户（幂等，不能关注自己）。"""
    if target_user_id == user.id:
        raise NotFoundError("不能关注自己")
    target = db.get(User, target_user_id)
    if target is None or target.status != 0:
        raise NotFoundError("用户不存在")
    exists = db.execute(
        select(UserFollow.id).where(
            UserFollow.user_id == user.id, UserFollow.target_user_id == target_user_id
        )
    ).scalar_one_or_none()
    if exists:
        return {"following": True, "count": _follower_count(db, target_user_id)}
    db.add(UserFollow(user_id=user.id, target_user_id=target_user_id))
    try:
        db.commit()
        notify(
            db, target_user_id, "follow", "有人关注了你",
            summary=f"{user.nickname or user.username} 关注了你",
            ref_id=user.id, actor_id=user.id,
        )
    except IntegrityError:
        db.rollback()  # 并发重复关注：唯一约束兜底
    return {"following": True, "count": _follower_count(db, target_user_id)}


def unfollow_user(db: Session, user: User, target_user_id: int) -> dict:
    """取消关注（幂等）。"""
    row = db.execute(
        select(UserFollow).where(
            UserFollow.user_id == user.id, UserFollow.target_user_id == target_user_id
        )
    ).scalar_one_or_none()
    if row is not None:
        db.delete(row)
        db.commit()
    return {"following": False, "count": _follower_count(db, target_user_id)}


def list_following(db: Session, user_id: int, page: int, page_size: int) -> dict:
    """我关注的用户列表（新在前）。"""
    stmt = (
        select(UserFollow)
        .where(UserFollow.user_id == user_id)
        .order_by(UserFollow.id.desc())
    )
    total = len(db.execute(stmt.with_only_columns(UserFollow.id)).scalars().all())
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    uids = [r.target_user_id for r in rows]
    users = (
        {u.id: u for u in db.execute(select(User).where(User.id.in_(uids))).scalars().all()}
        if uids else {}
    )
    items = []
    for r in rows:
        u = users.get(r.target_user_id)
        items.append({
            "id": r.target_user_id,
            "nickname": u.nickname if u else "",
            "username": u.username if u else "",
            "avatar_url": u.avatar_url if u else "",
            "followed_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_followers(db: Session, user_id: int, page: int, page_size: int) -> dict:
    """关注我（粉丝）的用户列表（新在前）。"""
    stmt = (
        select(UserFollow)
        .where(UserFollow.target_user_id == user_id)
        .order_by(UserFollow.id.desc())
    )
    total = len(db.execute(stmt.with_only_columns(UserFollow.id)).scalars().all())
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    uids = [r.user_id for r in rows]
    users = (
        {u.id: u for u in db.execute(select(User).where(User.id.in_(uids))).scalars().all()}
        if uids else {}
    )
    items = []
    for r in rows:
        u = users.get(r.user_id)
        items.append({
            "id": r.user_id,
            "nickname": u.nickname if u else "",
            "username": u.username if u else "",
            "avatar_url": u.avatar_url if u else "",
            "followed_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def follow_status(db: Session, user_id: int, target_user_id: int) -> bool:
    """是否已关注（他人主页用）。"""
    return (
        db.execute(
            select(UserFollow.id).where(
                UserFollow.user_id == user_id, UserFollow.target_user_id == target_user_id
            )
        ).scalar_one_or_none()
        is not None
    )


def _follower_count(db: Session, user_id: int) -> int:
    return db.execute(
        select(func.count(UserFollow.id)).where(UserFollow.target_user_id == user_id)
    ).scalar_one()
