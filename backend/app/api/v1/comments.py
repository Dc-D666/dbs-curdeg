"""评论接口：发评论/楼中楼回复/列表/删除（阶段 3）。"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_current_user_optional
from app.core.ratelimit import get_client_ip
from app.core.response import NotFoundError, ok
from app.db import get_db
from app.models.comment import Comment
from app.models.post import Post, POST_STATUS_NORMAL
from app.models.user import User
from app.schemas.post import CreateCommentRequest
from app.services import comment_service

router = APIRouter(tags=["comments"])


@router.post("/posts/{post_id}/comments")
def create_comment(
    post_id: int,
    payload: CreateCommentRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发表评论（需频道成员）。"""
    post = _get_post(db, post_id)
    return ok(data=comment_service.create_comment(
        db, post, user, payload, ip_region=get_client_ip(request),
    ), message="评论成功")


@router.get("/posts/{post_id}/comments")
def list_comments(
    post_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """顶层评论分页（楼层正序）。"""
    post = _get_post(db, post_id)
    uid = user.id if user else None
    return ok(data=comment_service.list_comments(db, post, page, page_size, uid))


@router.post("/comments/{comment_id}/replies")
def create_reply(
    comment_id: int,
    payload: CreateCommentRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """楼中楼回复（parent_id 自动取该评论）。"""
    comment = db.get(Comment, comment_id)
    if comment is None or comment.status != 0:
        raise NotFoundError("评论不存在")
    post = db.get(Post, comment.post_id)
    if post is None or post.status != POST_STATUS_NORMAL:
        raise NotFoundError("帖子不存在")
    payload = CreateCommentRequest(
        content=payload.content,
        parent_id=comment.id,
        reply_to_user_id=payload.reply_to_user_id or comment.author_id,
    )
    return ok(data=comment_service.create_comment(
        db, post, user, payload, ip_region=get_client_ip(request),
    ), message="回复成功")


@router.get("/comments/{comment_id}/replies")
def list_replies(
    comment_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """某条评论的楼中楼回复。"""
    comment = db.get(Comment, comment_id)
    if comment is None or comment.status != 0:
        raise NotFoundError("评论不存在")
    uid = user.id if user else None
    return ok(data=comment_service.list_replies(db, comment, page, page_size, uid))


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除评论（软删；本人或频道主/管理员）。"""
    comment = db.get(Comment, comment_id)
    if comment is None or comment.status != 0:
        raise NotFoundError("评论不存在")
    post = db.get(Post, comment.post_id)
    if post is None:
        raise NotFoundError("帖子不存在")
    comment_service.delete_comment(db, post, comment, user)
    return ok(message="评论已删除")


def _get_post(db: Session, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if post is None or post.status != POST_STATUS_NORMAL:
        raise NotFoundError("帖子不存在")
    return post
