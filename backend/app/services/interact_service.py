"""点赞/关注业务逻辑（阶段 3）。

幂等：likes 表 (post_id, comment_id, user_id) 唯一约束 + 先查后插 + IntegrityError 兜底，
重复点赞不重复计数；follows 表 (user_id, community_id) 唯一约束同理。
计数用 SQL 原子自增（UPDATE ... SET count = count + 1），并发下不丢计数。
"""
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.response import NotFoundError, ParamError
from app.models.comment import Comment
from app.models.community import Community
from app.models.follow import Follow
from app.models.like import Like
from app.models.post import Post, POST_STATUS_NORMAL
from app.models.user import User
from app.services import heat_service
from app.services.level_service import LEVEL_POINTS, add_level
from app.services.notify_service import notify
from app.services.post_service import _require_member

# post_id / comment_id 用 0 表示"无"（哨兵值，保证唯一约束生效，见 like.py 注释）


def like(db: Session, user: User, post_id: int | None = None, comment_id: int | None = None) -> dict:
    """点赞：post_id / comment_id 恰好一个；需频道成员且频道正常。返回最新计数。"""
    target, community_id = _resolve_target(db, post_id, comment_id)
    # 频道状态 + 成员身份（含禁言/拉黑）校验
    _require_member(db, community_id, user.id)

    post_id = post_id or 0
    comment_id = comment_id or 0
    exists = db.execute(
        select(Like.id).where(
            Like.post_id == post_id, Like.comment_id == comment_id, Like.user_id == user.id
        )
    ).scalar_one_or_none()
    if exists:
        return {"liked": True, "count": target.like_count}

    db.add(Like(post_id=post_id, comment_id=comment_id, user_id=user.id))
    _bump_count(db, target, +1)
    # 活跃等级：点赞 +1（仅新增点赞时，重复点赞不加）
    add_level(db, community_id, user.id, LEVEL_POINTS["like"])
    created = False
    try:
        db.commit()
        created = True
    except IntegrityError:
        db.rollback()  # 并发重复点赞：唯一约束兜底，不重复计数
    db.refresh(target)
    # 通知被赞者（自己赞自己不通知；ref_id 统一指向帖子，前端可跳转）
    if created and getattr(target, "author_id", None) != user.id:
        if isinstance(target, Post):
            summary, ref = target.title, target.id
        else:  # Comment
            summary, ref = (target.content or "评论内容")[:80], target.post_id
        notify(
            db, target.author_id, "like", "有人赞了你的内容",
            summary=summary, ref_id=ref, actor_id=user.id, community_id=community_id,
        )
    # 热度缓存：点赞数变化
    _bump_heat(db, target)
    return {"liked": True, "count": target.like_count}


def unlike(db: Session, user: User, post_id: int | None = None, comment_id: int | None = None) -> dict:
    """取消点赞（幂等：未点赞过也返回成功）。"""
    target, community_id = _resolve_target(db, post_id, comment_id)
    _require_member(db, community_id, user.id)

    post_id = post_id or 0
    comment_id = comment_id or 0
    row = db.execute(
        select(Like).where(
            Like.post_id == post_id, Like.comment_id == comment_id, Like.user_id == user.id
        )
    ).scalar_one_or_none()
    if row is None:
        return {"liked": False, "count": target.like_count}
    db.delete(row)
    _bump_count(db, target, -1)
    db.commit()
    db.refresh(target)
    # 热度缓存：点赞数变化
    _bump_heat(db, target)
    return {"liked": False, "count": target.like_count}


def follow(db: Session, user: User, community_id: int) -> dict:
    """关注频道（幂等）。"""
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
    except IntegrityError as e:
        db.rollback()
        if getattr(e.orig, "args", [None])[0] != 1062:  # 仅容忍唯一约束冲突，其余（如 FK）上抛
            raise
        return {"followed": True}
    # 通知频道主（自己关注自己的频道不通知）
    if community.owner_id != user.id:
        notify(
            db, community.owner_id, "follow", "有新的频道关注者",
            summary=f"关注了频道《{community.name}》", ref_id=community.id,
            actor_id=user.id, community_id=community.id,
        )
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


# ---------- 内部 ----------


def _resolve_target(
    db: Session, post_id: int | None, comment_id: int | None
) -> tuple[Post | Comment, int]:
    """解析点赞目标并校验存在性与参数二选一；返回 (目标对象, community_id)。"""
    if (post_id is None) == (comment_id is None):
        raise ParamError("post_id 与 comment_id 必须恰好提供一个")
    if post_id:
        target = db.get(Post, post_id)
        if target is None or target.status != POST_STATUS_NORMAL:
            raise NotFoundError("帖子不存在")
        return target, target.community_id
    target = db.get(Comment, comment_id)
    if target is None or target.status != 0:
        raise NotFoundError("评论不存在")
    post = db.get(Post, target.post_id)
    if post is None or post.status != POST_STATUS_NORMAL:
        raise NotFoundError("帖子不存在")
    return target, post.community_id


def _bump_count(db: Session, target: Post | Comment, delta: int) -> None:
    """原子增减计数（MySQL GREATEST 保证不为负）。"""
    model = Post if isinstance(target, Post) else Comment
    col = Post.like_count if isinstance(target, Post) else Comment.like_count
    if delta > 0:
        db.execute(update(model).where(model.id == target.id).values(like_count=col + 1))
    else:
        db.execute(
            update(model)
            .where(model.id == target.id)
            .values(like_count=func.greatest(0, col - 1))
        )


def _bump_heat(db: Session, target: Post | Comment) -> None:
    """点赞变化后更新热度缓存（评论点赞需定位其帖子）。"""
    if isinstance(target, Post):
        heat_service.bump(db, target, target.community_id)
    else:
        post = db.get(Post, target.post_id)
        if post:
            heat_service.bump(db, post, post.community_id)
