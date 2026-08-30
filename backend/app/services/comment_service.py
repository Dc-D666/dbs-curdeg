"""评论业务逻辑：顶层评论/楼中楼回复/删除（阶段 3）。"""
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.permissions import PERM_DELETE_COMMENT, require_perms
from app.core.response import ParamError
from app.models.comment import Comment
from app.models.like import CommentLike
from app.models.post import Post
from app.models.user import User
from app.schemas.post import CommentOut, CreateCommentRequest
from app.services import heat_service
from app.services.level_service import LEVEL_POINTS, add_level
from app.services.notify_service import notify
from app.services.op_log_service import log_op
from app.services.post_service import _require_member


def create_comment(
    db: Session, post: Post, user: User, payload: CreateCommentRequest, ip_region: str = ""
) -> CommentOut:
    """发评论：需频道成员且未被禁言；楼中楼只支持一层嵌套（对应原生）。"""
    _require_member(db, post.community_id, user.id)

    # 本地敏感词即时拦截（文档⑪）
    from app.services import sensitive_word_service

    if sensitive_word_service.ensure_switch_on(db) and sensitive_word_service.contains_sensitive(db, payload.content):
        hit = sensitive_word_service.check_text(db, payload.content)
        raise ParamError(f"评论包含敏感词，已被拦截（命中：{'、'.join(hit[:3])}）")

    parent = None
    if payload.parent_id:
        parent = db.get(Comment, payload.parent_id)
        if parent is None or parent.post_id != post.id or parent.status != 0:
            raise ParamError("回复的评论不存在")
        if parent.parent_id is not None:
            raise ParamError("楼中楼仅支持一层回复")
        if payload.reply_to_user_id is None:
            payload = CreateCommentRequest(
                content=payload.content, parent_id=payload.parent_id,
                reply_to_user_id=parent.author_id,
            )

    comment = Comment(
        post_id=post.id,
        author_id=user.id,
        parent_id=parent.id if parent else None,
        reply_to_user_id=payload.reply_to_user_id,
        content=payload.content,
        # P0：0普通 1楼中楼回复 2@提及；IP 属地（当前存客户端 IP 溯源）
        comment_type=2 if payload.reply_to_user_id else (1 if parent else 0),
        ip_region=ip_region,
    )
    db.add(comment)
    # 原子自增，避免并发 read-modify-write 丢计数
    db.execute(update(Post).where(Post.id == post.id).values(comment_count=Post.comment_count + 1))
    # 楼中楼回复：父评论 reply_count 原子 +1
    if parent:
        db.execute(
            update(Comment)
            .where(Comment.id == parent.id)
            .values(reply_count=Comment.reply_count + 1)
        )
    # 活跃等级：评论 +2
    add_level(db, post.community_id, user.id, LEVEL_POINTS["comment"])
    db.commit()
    db.refresh(comment)
    # 热度缓存：评论数变化
    db.refresh(post)
    heat_service.bump(db, post, post.community_id)
    # 通知：帖子作者（新评论）；楼中楼回复额外通知被回复者（与作者不同人时）
    preview = comment.content[:100]
    if post.author_id != user.id:
        notify(
            db, post.author_id, "comment", "你的帖子收到了新评论",
            summary=preview, ref_id=post.id, actor_id=user.id, community_id=post.community_id,
        )
    if parent and parent.author_id != user.id and parent.author_id != post.author_id:
        notify(
            db, parent.author_id, "comment", "你的评论收到了回复",
            summary=preview, ref_id=post.id, actor_id=user.id, community_id=post.community_id,
        )
    # AI 内容审核：评论异步入队快审（开关关闭时静默跳过）
    from app.ai.review import enqueue_comment_review

    enqueue_comment_review(comment.id)
    return comment_out(db, comment, user.id)


def list_comments(
    db: Session, post: Post, page: int, page_size: int, current_user_id: int | None
) -> dict:
    """顶层评论分页（楼层正序）。"""
    stmt = (
        select(Comment)
        .where(Comment.post_id == post.id, Comment.parent_id.is_(None), Comment.status == 0)
        .order_by(Comment.id)
    )
    total = len(db.execute(stmt.with_only_columns(Comment.id)).scalars().all())
    items = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return {
        "items": [comment_out(db, c, current_user_id) for c in items],
        "total": total, "page": page, "page_size": page_size,
    }


def list_replies(
    db: Session, comment: Comment, page: int, page_size: int, current_user_id: int | None
) -> dict:
    """某条评论的楼中楼回复（楼层正序）。"""
    stmt = (
        select(Comment)
        .where(Comment.parent_id == comment.id, Comment.status == 0)
        .order_by(Comment.id)
    )
    total = len(db.execute(stmt.with_only_columns(Comment.id)).scalars().all())
    items = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return {
        "items": [comment_out(db, c, current_user_id) for c in items],
        "total": total, "page": page, "page_size": page_size,
    }


def delete_comment(db: Session, post: Post, comment: Comment, user: User) -> None:
    """软删评论：本人，或拥有 delete_comment 权限的管理者；删顶层评论时级联软删其楼中楼回复。"""
    is_author = comment.author_id == user.id
    if is_author:
        _require_member(db, post.community_id, user.id)
    else:
        require_perms(db, post.community_id, user, PERM_DELETE_COMMENT)

    removed = 1
    if comment.parent_id is None:
        # 顶层评论：级联软删楼中楼回复，计数一并扣减
        reply_ids = db.execute(
            select(Comment.id).where(Comment.parent_id == comment.id, Comment.status == 0)
        ).scalars().all()
        if reply_ids:
            db.execute(
                update(Comment)
                .where(Comment.id.in_(reply_ids))
                .values(status=1)
            )
            removed += len(reply_ids)
    comment.status = 1
    # 原子递减（不为负）
    db.execute(
        update(Post)
        .where(Post.id == post.id)
        .values(comment_count=func.greatest(0, Post.comment_count - removed))
    )
    if not is_author:
        log_op(db, post.community_id, user.id, "delete_comment", "comment", comment.id, {"author_id": comment.author_id})
    db.commit()
    # 热度缓存：评论数减少
    db.refresh(post)
    heat_service.bump(db, post, post.community_id)


def comment_out(db: Session, comment: Comment, current_user_id: int | None) -> CommentOut:
    """评论输出增强：作者信息、回复目标、我的点赞状态。"""
    out = CommentOut.model_validate(comment)
    author = db.get(User, comment.author_id)
    if author:
        out.author_nickname = author.nickname or author.username
        out.author_avatar = author.avatar_url
    if comment.reply_to_user_id:
        ru = db.get(User, comment.reply_to_user_id)
        if ru:
            out.reply_to_nickname = ru.nickname or ru.username
    if current_user_id:
        liked = db.execute(
            select(CommentLike.id).where(
                CommentLike.comment_id == comment.id, CommentLike.user_id == current_user_id
            )
        ).scalar_one_or_none()
        out.is_liked = liked is not None
    return out
