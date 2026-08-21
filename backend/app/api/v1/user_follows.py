"""用户互关接口（文档⑨用户关注，P0）：关注/取关/我的关注/我的粉丝/状态。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_current_user_optional
from app.core.response import ok
from app.db import get_db
from app.models.user import User
from app.services import user_follow_service

router = APIRouter(tags=["user_follows"])


@router.post("/users/{user_id}/follow")
def follow_user(
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """关注用户（幂等）。"""
    return ok(data=user_follow_service.follow_user(db, user, user_id), message="已关注")


@router.delete("/users/{user_id}/follow")
def unfollow_user(
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消关注（幂等）。"""
    return ok(data=user_follow_service.unfollow_user(db, user, user_id), message="已取消关注")


@router.get("/me/following")
def my_following(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我关注的用户列表。"""
    return ok(data=user_follow_service.list_following(db, user.id, page, page_size))


@router.get("/me/followers")
def my_followers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的粉丝列表。"""
    return ok(data=user_follow_service.list_followers(db, user.id, page, page_size))


@router.get("/users/{user_id}/follow-status")
def follow_status(
    user_id: int,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """查询我是否已关注该用户（未登录返回 false）。"""
    following = user is not None and user_follow_service.follow_status(db, user.id, user_id)
    return ok(data={"following": following})
