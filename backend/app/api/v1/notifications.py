"""通知接口：列表 / 未读数 / 单条已读 / 全部已读 / 通知开关（阶段 5）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import ok
from app.db import get_db
from app.models.user import User
from app.schemas.notification import NotifySettingsUpdate
from app.services import notify_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """通知分页（未读在前，时间倒序）。"""
    return ok(data=notify_service.list_notifications(db, user.id, page, page_size))


@router.get("/unread-count")
def get_unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """未读通知数（顶部角标轮询用）。"""
    return ok(data={"count": notify_service.unread_count(db, user.id)})


@router.post("/{notification_id}/read")
def read_notification(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """标记单条已读。"""
    notify_service.mark_read(db, user.id, notification_id)
    return ok(message="已读")


@router.post("/read-all")
def read_all_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """全部标记已读，返回本次标记条数。"""
    return ok(data={"marked": notify_service.mark_all_read(db, user.id)}, message="全部已读")


@router.get("/settings")
def get_notify_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的通知开关。"""
    return ok(data=notify_service.get_settings(db, user))


@router.put("/settings")
def update_notify_settings(
    payload: NotifySettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新通知开关（部分更新）。"""
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    return ok(data=notify_service.update_settings(db, user, patch), message="设置已保存")
