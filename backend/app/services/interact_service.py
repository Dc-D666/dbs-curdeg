"""点赞/关注业务逻辑（阶段 3）。

幂等：likes 表 (post_id, comment_id, user_id) 唯一约束 + 先查后插 + IntegrityError 兜底，
重复点赞不重复计数；follows 表 (user_id, community_id) 唯一约束同理。
"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.response import NotFoundError, ParamError
from app.models.comment import Comment
from app.models.community import Community
from app.models.follow import Follow
from app.models.like import Like
from app.models.post import Post, POST_STATUS_NORMAL
from app.models.user import User

# post_id / comment_id 用 0 表示"无"（哨兵值，保证唯一约束生效，见 like.py 注释）


def like(db: Session, user: User, post_id: int | None = None, comment_id: int | None = None) -> dict:
    """点赞：post_id / comment_id 恰好一个。返回最新计数。"""
    if (post_id is None) == (comment_id is None):
        raise ParamError("post_id 与 comment_id 必须恰好提供一个")
    post_id = post_id or 0
    comment_id = comment_id or 0

    target: Post | Comment
    if post_id:
        target = db.get(Post, post_id)
        if target is None or target.status != POST_STATUS_NORMAL:
            raise NotFoundError("帖子不存在")
    else:
        target = db.get(Comment, comment_id)
        if target is None or target.status != 0:
            raise NotFoundError("评论不存在")

    created = _insert_like(db, user.id, post_id, comment_id)
    if created:
        target.like_count += 1
        db.commit()
        db.refresh(target)
    return {"liked": True, "count": target.like_count}


def unlike(db: Session, user: User, post_id: int | None = None, comment_id: int | None = None) -> dict:
    """取消点赞（幂等：未点赞过也返回成功）。"""
    if (post_id is None) == (comment_id is None):
        raise ParamError("post_id 与 comment_id 必须恰好提供一个")
    post_id = post_id or 0
    comment_id = comment_id or 0

    row = db.execute(
        select(Like).where(
            Like.post_id == post_id, Like.comment_id == comment_id, Like.user_id == user.id
        )
    ).scalar_one_or_none()
    if row is None:
        target = _load_target(db, post_id, comment_id)
        count = target.like_count if target is not None else 0
        return {"liked": False, "count": count}

    target = _load_target(db, post_id, comment_id)
    db.delete(row)
    if target is not None:
        target.like_count = max(0, target.like_count - 1)
    db.commit()
    return {"liked": False, "count": target.like_count if target is not None else 0}


def follow(db: Session, user: User, community_id: int) -> dict:
    """关注频道（幂等）。返回关注状态与关注数。"""
    community = db.get(Community, community_id)
    if community is None or community.status != 0:
        raise NotFoundError("频道不存在")
    exists = db.execute(
        select(Follow.id).where(Follow.user_id == user.id, Follow.community_id == community_id)
    ).scalar_one_or_none()
    if exists:
        return {"followed": True}
    db.add(Follow(user_id=user.id, community_id=community_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # 并发重复关注
    return {"followed": True}


def unfollow(db: Session, user: User, community_id: int) -> dict:
    """取消关注（幂等）。"""
    row = db.execute(
        select(Follow).where(Follow.user_id == user.id, Follow.community_id == community_id)
    ).scalar_one_or_none()
    if row is not None:
        db.delete(row)
        db.commit()
    return {"followed": False}


def _insert_like(db: Session, user_id: int, post_id: int, comment_id: int) -> bool:
    """插入点赞记录；已存在或并发冲突返回 False。"""
    exists = db.execute(
        select(Like.id).where(
            Like.post_id == post_id, Like.comment_id == comment_id, Like.user_id == user_id
        )
    ).scalar_one_or_none()
    if exists:
        return False
    db.add(Like(post_id=post_id, comment_id=comment_id, user_id=user_id))
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def _load_target(db: Session, post_id: int, comment_id: int) -> Post | Comment | None:
    if post_id:
        return db.get(Post, post_id)
    return db.get(Comment, comment_id)
