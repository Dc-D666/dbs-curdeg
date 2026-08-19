"""频道接口：创建/列表/详情/编辑/解散/加入/退出。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_current_user_optional
from app.core.response import NotFoundError, ok
from app.db import get_db
from app.models.community import Community
from app.models.user import User
from app.schemas.community import CreateCommunityRequest, UpdateCommunityRequest, UpdateCommunityStatusRequest
from app.services import community_service

router = APIRouter(prefix="/communities", tags=["communities"])


@router.post("")
def create_community(
    payload: CreateCommunityRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建频道（自动成为 owner + 初始化默认身份组）。"""
    return ok(data=community_service.create_community(db, user, payload), message="频道创建成功")


@router.get("")
def list_communities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """频道列表（公开，含我加入标记）。"""
    uid = user.id if user else None
    return ok(data=community_service.list_communities(db, page, page_size, uid))


@router.get("/{community_id}")
def get_community(
    community_id: int,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """频道详情（含版块列表 + 我的成员身份）。"""
    community = db.get(Community, community_id)
    if community is None:
        raise NotFoundError("频道不存在")
    uid = user.id if user else None
    return ok(data=community_service.get_community(db, community_id, uid))


@router.put("/{community_id}")
def update_community(
    community_id: int,
    payload: UpdateCommunityRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """编辑频道设置（仅 owner）。"""
    community = db.get(Community, community_id)
    if community is None:
        raise NotFoundError("频道不存在")
    return ok(data=community_service.update_community(db, community, user, payload))


@router.delete("/{community_id}")
def dissolve_community(
    community_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """解散频道（仅 owner，软删）。"""
    community = db.get(Community, community_id)
    if community is None:
        raise NotFoundError("频道不存在")
    community_service.dissolve_community(db, community, user)
    return ok(message="频道已解散")


@router.put("/{community_id}/status")
def update_community_status(
    community_id: int,
    payload: UpdateCommunityStatusRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """频道状态调整：0正常/1关闭(owner) / 2违规封禁(系统管理员)。"""
    community = db.get(Community, community_id)
    if community is None:
        raise NotFoundError("频道不存在")
    return ok(data=community_service.update_community_status(db, community, user, payload.status))


@router.post("/{community_id}/join")
def join_community(
    community_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """加入频道（自由/审核/邀请三种方式）。"""
    community = db.get(Community, community_id)
    if community is None:
        raise NotFoundError("频道不存在")
    return ok(data=community_service.join_community(db, community, user))


@router.post("/{community_id}/leave")
def leave_community(
    community_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """退出频道（owner 只能解散）。"""
    community = db.get(Community, community_id)
    if community is None:
        raise NotFoundError("频道不存在")
    community_service.leave_community(db, community, user)
    return ok(message="已退出频道")
