"""管理动作接口（阶段 4 + P0）：禁言/解除/踢出/拉黑/解除/操作日志/导出。

全部走 require_perms：shutup / kick / member_manage / moderate。
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import NotFoundError, ok
from app.db import get_db
from app.models.community import Community
from app.models.user import User
from app.services import manage_service, op_log_service

router = APIRouter(prefix="/communities/{community_id}", tags=["manage"])


class ShutupRequest(BaseModel):
    hours: int = Field(ge=1, le=720, description="禁言时长（小时，最长 30 天）")


def _get_community(db: Session, community_id: int) -> Community:
    community = db.get(Community, community_id)
    if community is None or community.status != 0:
        raise NotFoundError("频道不存在")
    return community


@router.post("/members/{user_id}/shutup")
def shutup(
    community_id: int,
    user_id: int,
    payload: ShutupRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """禁言成员（shutup 权限）。"""
    _get_community(db, community_id)
    return ok(data=manage_service.shutup(db, community_id, user, user_id, payload.hours), message="已禁言")


@router.post("/members/{user_id}/unshutup")
def unshutup(
    community_id: int,
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """解除禁言（shutup 权限）。"""
    _get_community(db, community_id)
    return ok(data=manage_service.unshutup(db, community_id, user, user_id), message="已解除禁言")


@router.post("/members/{user_id}/kick")
def kick(
    community_id: int,
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """踢出成员（kick 权限）：无法再发帖与重新加入。"""
    _get_community(db, community_id)
    return ok(data=manage_service.kick(db, community_id, user, user_id), message="已踢出")


@router.post("/members/{user_id}/block")
def block(
    community_id: int,
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """拉黑成员（member_manage 权限）：无法再发帖与重新加入。"""
    _get_community(db, community_id)
    return ok(data=manage_service.block(db, community_id, user, user_id), message="已拉黑")


@router.post("/members/{user_id}/unblock")
def unblock(
    community_id: int,
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """解除拉黑（member_manage 权限）。"""
    _get_community(db, community_id)
    return ok(data=manage_service.unblock(db, community_id, user, user_id), message="已解除拉黑")


@router.get("/ops")
def ops(
    community_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    action: str | None = Query(None, max_length=32),
    target_type: str | None = Query(None, max_length=32),
    operator_id: int | None = Query(None, gt=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """操作日志列表（moderate 权限，所有管理动作留痕；支持多条件过滤）。"""
    _get_community(db, community_id)
    from app.core.permissions import PERM_MODERATE, require_perms

    require_perms(db, community_id, user, PERM_MODERATE)
    return ok(data=op_log_service.list_ops(
        db, community_id, page, page_size,
        action=action, target_type=target_type, operator_id=operator_id,
    ))


@router.get("/ops/export")
def export_ops(
    community_id: int,
    action: str | None = Query(None, max_length=32),
    target_type: str | None = Query(None, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出操作日志 CSV（moderate 权限，文档⑱日志导出）。"""
    _get_community(db, community_id)
    from app.core.permissions import PERM_MODERATE, require_perms

    require_perms(db, community_id, user, PERM_MODERATE)
    csv_text = op_log_service.export_ops(db, community_id, action=action, target_type=target_type)
    filename = f"ops_{community_id}.csv"
    return PlainTextResponse(
        "\ufeff" + csv_text,  # BOM 让 Excel 正确识别 UTF-8
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
