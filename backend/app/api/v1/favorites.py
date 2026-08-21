"""收藏接口（文档⑨收藏记录，P0）：收藏/取消收藏/我的收藏列表。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import ok
from app.db import get_db
from app.models.user import User
from app.services import favorite_service

router = APIRouter(tags=["favorites"])


class FavoriteRequest(BaseModel):
    group_name: str = Field(default="默认", max_length=32)


@router.post("/posts/{post_id}/favorite")
def favorite_post(
    post_id: int,
    payload: FavoriteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """收藏帖子（幂等）。"""
    return ok(
        data=favorite_service.favorite(db, user, post_id, payload.group_name),
        message="已收藏",
    )


@router.delete("/posts/{post_id}/favorite")
def unfavorite_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消收藏（幂等）。"""
    return ok(data=favorite_service.unfavorite(db, user, post_id), message="已取消收藏")


@router.get("/me/favorites")
def my_favorites(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的收藏列表。"""
    return ok(data=favorite_service.list_favorites(db, user, page, page_size))
