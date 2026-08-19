"""互动接口：点赞/取消点赞/关注频道/取消关注（阶段 3）。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import ok
from app.db import get_db
from app.models.user import User
from app.services import interact_service

router = APIRouter(tags=["interact"])


class LikeRequest(BaseModel):
    post_id: int | None = Field(default=None, gt=0)
    comment_id: int | None = Field(default=None, gt=0)


class FollowRequest(BaseModel):
    community_id: int = Field(gt=0)


@router.post("/likes")
def like(
    payload: LikeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """点赞（帖子或评论，幂等不重复计数）。"""
    return ok(data=interact_service.like(db, user, payload.post_id, payload.comment_id), message="点赞成功")


@router.delete("/likes")
def unlike(
    post_id: int | None = Query(None, gt=0),
    comment_id: int | None = Query(None, gt=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消点赞（幂等）。"""
    return ok(data=interact_service.unlike(db, user, post_id, comment_id), message="已取消点赞")


@router.post("/follows")
def follow(
    payload: FollowRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """关注频道（幂等）。"""
    return ok(data=interact_service.follow(db, user, payload.community_id), message="关注成功")


@router.delete("/follows")
def unfollow(
    community_id: int = Query(gt=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消关注（幂等）。"""
    return ok(data=interact_service.unfollow(db, user, community_id), message="已取消关注")
