"""评论业务逻辑：顶层评论/楼中楼回复/删除（阶段 3）。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.response import ParamError, PermissionError_
from app.models.comment import Comment
from app.models.like import Like
from app.models.member import MEMBER_ADMIN, MEMBER_OWNER, Member
from app.models.post import Post
from app.models.user import User
from app.schemas.post import CommentOut, CreateCommentRequest
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
    post.comment_count += 1
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
    """软删评论：本人或频道主/管理员。"""
    member = db.execute(
        select(Member).where(Member.community_id == post.community_id, Member.user_id == user.id)
    ).scalar_one_or_none()
    if member is None:
        raise PermissionError_("只有频道成员可以执行此操作")
    if comment.author_id != user.id and member.member_type not in (MEMBER_OWNER, MEMBER_ADMIN):
        raise PermissionError_("只能删除自己的评论，或需要频道主/管理员权限")
    comment.status = 1
    post.comment_count = max(0, post.comment_count - 1)
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
