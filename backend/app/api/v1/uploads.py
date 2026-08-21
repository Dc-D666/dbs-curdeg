"""上传接口：图片上传（用户头像、频道头像/封面共用）。"""
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import ParamError, ok
from app.db import get_db
from app.models.user import User
from app.services import upload_service

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("")
def upload_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传图片，返回可访问 URL。"""
    limit = upload_service.configured_max_size(db)
    if file.size and file.size > limit:
        raise ParamError(f"图片大小不能超过 {limit // (1024 * 1024)}MB")
    url = upload_service.save_image(file, max_size=limit)
    return ok(data={"url": url}, message="上传成功")
