"""帖子附件接口（文档⑦，P0）：上传/绑定/列表/删除。"""
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import ok
from app.db import get_db
from app.models.user import User
from app.services import attachment_service, upload_service

router = APIRouter(tags=["attachments"])


class CreateAttachmentRequest(BaseModel):
    media_type: int = Field(default=1, ge=1, le=3, description="1图片 2视频 3文件")
    url: str = Field(min_length=1, max_length=255)
    thumb_url: str = Field(default="", max_length=255)
    width: int = Field(default=0, ge=0)
    height: int = Field(default=0, ge=0)
    file_size: int = Field(default=0, ge=0)
    duration: int = Field(default=0, ge=0)


class AttachmentOut(BaseModel):
    id: int
    post_id: int
    media_type: int
    url: str
    thumb_url: str
    width: int
    height: int
    file_size: int
    duration: int
    sort_order: int

    model_config = {"from_attributes": True}


@router.post("/posts/{post_id}/attachments")
def create_attachment(
    post_id: int,
    payload: CreateAttachmentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """为帖子绑定附件（作者本人或频道管理者）。"""
    post = attachment_service._get_post(db, post_id)
    att = attachment_service.create_attachment(
        db, post, user,
        media_type=payload.media_type,
        url=payload.url,
        thumb_url=payload.thumb_url,
        width=payload.width,
        height=payload.height,
        file_size=payload.file_size,
        duration=payload.duration,
    )
    return ok(data=AttachmentOut.model_validate(att), message="附件已添加")


@router.post("/posts/{post_id}/attachments/upload")
def upload_attachment(
    post_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传附件文件并绑定到帖子（图片/视频/文件，作者本人或频道管理者）。"""
    post = attachment_service._get_post(db, post_id)
    saved = upload_service.save_attachment(file)
    att = attachment_service.create_attachment(
        db, post, user,
        media_type=saved["media_type"],
        url=saved["url"],
        file_size=saved["file_size"],
    )
    return ok(data=AttachmentOut.model_validate(att), message="附件已上传")


@router.get("/posts/{post_id}/attachments")
def list_attachments(post_id: int, db: Session = Depends(get_db)):
    """帖子附件列表（公开可读）。"""
    attachment_service._get_post(db, post_id)
    items = attachment_service.list_attachments(db, post_id)
    return ok(data=[AttachmentOut.model_validate(a) for a in items])


@router.delete("/attachments/{attachment_id}")
def delete_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除附件（作者本人或频道主/管理员）。"""
    attachment_service.delete_attachment(db, user, attachment_id)
    return ok(message="附件已删除")
