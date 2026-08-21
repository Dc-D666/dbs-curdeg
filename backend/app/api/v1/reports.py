"""举报接口（文档⑫举报申诉管理，P0）。

- 用户：POST /reports 提交举报；GET /me/reports 我的举报
- 管理员：GET /admin/reports 列表；POST /admin/reports/{id}/handle 受理/办结/驳回
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import ok
from app.db import get_db
from app.models.user import User
from app.services import report_service

router = APIRouter(tags=["reports"])


class CreateReportRequest(BaseModel):
    target_type: int = Field(ge=1, le=4, description="1帖子 2评论 3用户 4频道")
    target_id: int = Field(gt=0)
    reason_type: str = Field(default="其他", max_length=32)
    detail: str = Field(default="", max_length=500)
    evidence: list[str] = Field(default_factory=list, max_length=9)


class HandleReportRequest(BaseModel):
    action: str = Field(pattern="^(processing|done|rejected)$")
    result: str = Field(default="", max_length=255)


@router.post("/reports")
def create_report(
    payload: CreateReportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交举报。"""
    report = report_service.create_report(
        db, user,
        payload.target_type, payload.target_id,
        payload.reason_type, payload.detail, payload.evidence,
    )
    return ok(data={"id": report.id}, message="举报已提交，我们会尽快处理")


@router.get("/me/reports")
def my_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的举报记录。"""
    return ok(data=report_service.list_my_reports(db, user.id, page, page_size))


@router.get("/admin/reports")
def admin_reports(
    status: int | None = Query(None, ge=0, le=3),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """举报记录列表（需系统管理员）。"""
    from app.core.response import PermissionError_

    if user.user_type != 1:
        raise PermissionError_("需要系统管理员权限")
    return ok(data=report_service.list_reports(db, status, page, page_size))


@router.post("/admin/reports/{report_id}/handle")
def admin_handle_report(
    report_id: int,
    payload: HandleReportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """受理/办结/驳回举报（需系统管理员），并通知举报人结果。"""
    from app.core.response import PermissionError_

    if user.user_type != 1:
        raise PermissionError_("需要系统管理员权限")
    report = report_service.handle_report(db, user, report_id, payload.action, payload.result)
    return ok(data={"id": report.id, "status": report.status}, message="已处理")
