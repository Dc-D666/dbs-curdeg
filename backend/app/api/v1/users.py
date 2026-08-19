"""用户接口：个人资料查看/编辑、他人主页。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import NotFoundError, ok
from app.db import get_db
from app.models.user import User
from app.schemas.user import UpdateProfileRequest, UserOut
from app.services import auth_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    """当前登录用户资料。"""
    return ok(data=auth_service.get_user_out(user))


@router.put("/me")
def update_me(
    payload: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新个人资料。"""
    return ok(data=auth_service.update_profile(db, user, payload))


@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    """他人主页（公开资料）。"""
    user = db.get(User, user_id)
    if user is None or user.status != 0:
        raise NotFoundError("用户不存在")
    return ok(data=auth_service.get_user_out(user))
