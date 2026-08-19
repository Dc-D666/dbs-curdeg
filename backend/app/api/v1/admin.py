"""运营管理接口（阶段 7）：数据看板 / 审核记录管理（系统管理员 user_type=1）。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import PermissionError_, ok
from app.db import get_db
from app.models.user import User
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    """系统管理员（user_type=1）才能访问运营接口。"""
    if user.user_type != 1:
        raise PermissionError_("需要系统管理员权限")
    return user


class HandleReviewRequest(BaseModel):
    approve: bool


@router.get("/stats")
def admin_stats(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """运营看板：全局用户/频道/内容/互动统计 + 近 7 天发帖趋势 + Top 频道。"""
    return ok(data=admin_service.overview_stats(db))


@router.get("/reviews")
def admin_reviews(
    status: int | None = Query(None, ge=0, le=3),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """审核记录列表（可按状态过滤：0待审 1通过 2驳回 3转人工）。"""
    return ok(data=admin_service.list_reviews(db, status, page, page_size))


@router.post("/reviews/{review_id}/handle")
def admin_handle_review(
    review_id: int,
    payload: HandleReviewRequest,
    reviewer: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """人工处理转人工复审的记录（通过恢复帖子 / 维持驳回），并通知作者。"""
    admin_service.handle_review(db, reviewer, review_id, payload.approve)
    return ok(message="已处理" if payload.approve else "已驳回")
