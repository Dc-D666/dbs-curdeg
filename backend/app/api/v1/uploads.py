"""上传接口：图片上传（用户头像、频道头像/封面共用）。"""
from fastapi import APIRouter, Depends, File, UploadFile

from app.core.deps import get_current_user
from app.core.response import ok
from app.models.user import User
from app.services import upload_service

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("")
def upload_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """上传图片，返回可访问 URL。"""
    url = upload_service.save_image(file)
    return ok(data={"url": url}, message="上传成功")
