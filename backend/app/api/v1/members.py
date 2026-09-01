"""成员接口：列表/加入审核/退出/我的成员信息。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import NotFoundError, ok
from app.db import get_db
from app.models.community import Community
from app.models.join_request import JoinRequest
from app.models.member import Member
from app.models.role import Role
from app.models.user import User
from app.schemas.community import HandleJoinRequest
from app.services import community_service

router = APIRouter(prefix="/communities/{community_id}", tags=["members"])


def _get_community(db: Session, community_id: int) -> Community:
    community = db.get(Community, community_id)
    if community is None or community.status != 0:
        raise NotFoundError("频道不存在")
    return community


class UpdateMyMemberRequest(BaseModel):
    nickname: str = Field(min_length=0, max_length=64)


@router.get("/my-member")
def my_member(
    community_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的频道成员信息（等级/昵称/身份/加入时间），供频道设置页「我的资料/我的等级」。"""
    _get_community(db, community_id)
    m = db.execute(
        select(Member).where(Member.community_id == community_id, Member.user_id == user.id)
    ).scalar_one_or_none()
    if m is None:
        raise NotFoundError("你还不是该频道成员")
    role = db.get(Role, m.role_id) if m.role_id else None
    return ok(data={
        "member_id": m.id,
        "level": m.level,
        "member_type": m.member_type,
        "nickname": m.nickname,
        "role_id": m.role_id,
        "role_name": role.name if role else "",
        "role_color": role.color if role else "",
        "is_owner": m.member_type == 0,
        "join_time": m.join_time.isoformat() if m.join_time else None,
    })


@router.put("/my-member")
def update_my_member(
    community_id: int,
    payload: UpdateMyMemberRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新我的频道内昵称（我的资料）。"""
    _get_community(db, community_id)
    m = db.execute(
        select(Member).where(Member.community_id == community_id, Member.user_id == user.id)
    ).scalar_one_or_none()
    if m is None:
        raise NotFoundError("你还不是该频道成员")
    m.nickname = payload.nickname.strip()
    db.commit()
    return ok(message="昵称已更新")


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


@router.get("/blacklist")
def list_blacklist(
    community_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    keyword: str | None = Query(None, max_length=64),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """黑名单列表（is_blocked=True；需 member_manage 权限）。"""
    community = _get_community(db, community_id)
    from app.core.permissions import PERM_MEMBER_MANAGE, require_perms

    require_perms(db, community_id, user, PERM_MEMBER_MANAGE)
    return ok(data=community_service.list_blacklist(db, community, page, page_size, keyword))


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
