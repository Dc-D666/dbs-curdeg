"""收藏业务（文档⑨收藏记录，P0）。

幂等：(user_id, post_id) 唯一约束 + 先查后插 + IntegrityError 兜底；
posts.favorite_count 用 SQL 原子自增，并发下不丢计数。
"""
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.response import NotFoundError, ParamError
from app.models.favorite import Favorite
from app.models.post import Post, POST_STATUS_NORMAL
from app.models.user import User


def favorite(db: Session, user: User, post_id: int, group_name: str = "默认") -> dict:
    """收藏帖子（幂等）：需帖子正常。返回最新收藏数与状态。"""
    post = db.get(Post, post_id)
    if post is None or post.status != POST_STATUS_NORMAL:
        raise NotFoundError("帖子不存在")
    exists = db.execute(
        select(Favorite.id).where(Favorite.user_id == user.id, Favorite.post_id == post_id)
    ).scalar_one_or_none()
    if exists:
        return {"favorited": True, "count": post.favorite_count}
    db.add(
        Favorite(
            user_id=user.id,
            post_id=post_id,
            group_name=(group_name or "默认")[:32],
        )
    )
    db.execute(update(Post).where(Post.id == post.id).values(favorite_count=Post.favorite_count + 1))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # 并发重复收藏：唯一约束兜底，不重复计数
    db.refresh(post)
    return {"favorited": True, "count": post.favorite_count}


def unfavorite(db: Session, user: User, post_id: int) -> dict:
    """取消收藏（幂等）。返回最新收藏数。"""
    post = db.get(Post, post_id)
    if post is None or post.status != POST_STATUS_NORMAL:
        raise NotFoundError("帖子不存在")
    row = db.execute(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.post_id == post_id)
    ).scalar_one_or_none()
    if row is None:
        return {"favorited": False, "count": post.favorite_count}
    db.delete(row)
    db.execute(
        update(Post)
        .where(Post.id == post.id)
        .values(favorite_count=func.greatest(0, Post.favorite_count - 1))
    )
    db.commit()
    db.refresh(post)
    return {"favorited": False, "count": post.favorite_count}


def list_favorites(
    db: Session, user: User, page: int, page_size: int
) -> dict:
    """我的收藏列表（新在前），返回帖子 id + 标题摘要。"""
    stmt = (
        select(Favorite)
        .where(Favorite.user_id == user.id)
        .order_by(Favorite.id.desc())
    )
    total = len(db.execute(stmt.with_only_columns(Favorite.id)).scalars().all())
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    post_ids = [r.post_id for r in rows]
    posts = (
        {p.id: p for p in db.execute(select(Post).where(Post.id.in_(post_ids))).scalars().all()}
        if post_ids else {}
    )
    items = []
    for r in rows:
        p = posts.get(r.post_id)
        items.append({
            "favorite_id": r.id,
            "group_name": r.group_name,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "post_id": r.post_id,
            "post_title": p.title if p else "",
            "post_status": p.status if p else -1,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def favorite_status(db: Session, user: User, post_id: int) -> bool:
    """查询是否已收藏（详情页用）。"""
    return (
        db.execute(
            select(Favorite.id).where(Favorite.user_id == user.id, Favorite.post_id == post_id)
        ).scalar_one_or_none()
        is not None
    )
