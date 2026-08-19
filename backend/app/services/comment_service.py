"""评论业务逻辑：顶层评论/楼中楼回复/删除（阶段 3）。"""
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.permissions import PERM_DELETE_COMMENT, require_perms
from app.core.response import ParamError
from app.models.comment import Comment
from app.models.like import Like
from app.models.post import Post
from app.models.user import User
from app.schemas.post import CommentOut, CreateCommentRequest
from app.services.op_log_service import log_op
from app.services.post_service import _require_member


def create_comment(
    db: Session, post: Post, user: User, payload: CreateCommentRequest
) -> CommentOut:
    """发评论：需频道成员且未被禁言；楼中楼只支持一层嵌套（对应原生）。"""
    _require_member(db, post.community_id, user.id)

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
    )
    db.add(comment)
    # 原子自增，避免并发 read-modify-write 丢计数
    db.execute(update(Post).where(Post.id == post.id).values(comment_count=Post.comment_count + 1))
    db.commit()
    db.refresh(comment)
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
            select(Like.id).where(
                Like.comment_id == comment.id, Like.post_id == 0, Like.user_id == current_user_id
            )
        ).scalar_one_or_none()
        out.is_liked = liked is not None
    return out
