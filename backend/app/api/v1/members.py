"""成员接口：列表/加入审核/退出。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import NotFoundError, ok
from app.db import get_db
from app.models.community import Community
from app.models.join_request import JoinRequest
from app.models.user import User
from app.schemas.community import HandleJoinRequest
from app.services import community_service

router = APIRouter(prefix="/communities/{community_id}", tags=["members"])


def _get_community(db: Session, community_id: int) -> Community:
    community = db.get(Community, community_id)
    if community is None or community.status != 0:
        raise NotFoundError("频道不存在")
    return community


@router.get("/members")
def list_members(
    community_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    keyword: str | None = Query(None, max_length=64, description="按用户名或昵称模糊搜索"),
    db: Session = Depends(get_db),
):
    """成员列表（公开；支持按用户名/昵称模糊搜索）。"""
    community = _get_community(db, community_id)
    return ok(data=community_service.list_members(db, community, page, page_size, keyword))


@router.get("/join-requests")
def list_join_requests(
    community_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """加入申请列表（仅 owner/admin）。"""
    community = _get_community(db, community_id)
    return ok(data=community_service.list_join_requests(db, community, user, page, page_size))


@router.post("/join-requests/{request_id}")
def handle_join_request(
    community_id: int,
    request_id: int,
    payload: HandleJoinRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """审核加入申请（通过/驳回）。"""
    community = _get_community(db, community_id)
    req = db.get(JoinRequest, request_id)
    if req is None or req.community_id != community_id:
        raise NotFoundError("申请不存在")
    community_service.handle_join_request(db, community, user, req, payload.approve)
    return ok(message="已通过" if payload.approve else "已驳回")
