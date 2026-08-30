"""用户接口：个人资料查看/编辑、他人主页、头像上传。"""
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_current_user_optional
from app.core.response import NotFoundError, ok
from app.db import get_db
from app.models.user import User
from app.schemas.user import PublicUserOut, UpdateProfileRequest, UserOut
from app.services import auth_service, post_service, upload_service

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


@router.post("/me/avatar")
def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传头像：保存图片并更新 avatar_url。"""
    url = upload_service.save_image(file)
    user.avatar_url = url
    db.commit()
    db.refresh(user)
    return ok(data=auth_service.get_user_out(user), message="头像已更新")


@router.post("/me/deactivate")
def deactivate_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """注销账号（软注销：登录态立即失效，后续登录被拒）。"""
    auth_service.deactivate(db, user)
    return ok(message="账号已注销")


@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    """他人主页（公开资料，不含邮箱等隐私字段）。"""
    user = db.get(User, user_id)
    if user is None or user.status != 0:
        raise NotFoundError("用户不存在")
    return ok(data=PublicUserOut.model_validate(user))


@router.get("/{user_id}/posts")
def get_user_posts(
    user_id: int,
    cursor: str | None = Query(None, description="游标：最后帖子 id"),
    page_size: int = Query(20, ge=1, le=50),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """某用户发布的帖子（他人主页「TA 的帖子」，latest）。"""
    target = db.get(User, user_id)
    if target is None or target.status != 0:
        raise NotFoundError("用户不存在")
    return ok(data=post_service.user_posts(db, user_id, cursor, page_size, user.id if user else None))
