"""频道接口：创建/列表/详情/编辑/解散/加入/退出/转让/全员禁言。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_current_user_optional
from app.core.response import NotFoundError, PermissionError_, ok
from app.db import get_db
from app.models.community import Community
from app.models.user import User
from app.schemas.community import CreateCommunityRequest, UpdateCommunityRequest, UpdateCommunityStatusRequest
from app.services import community_service
from app.services.ops_service import can_view_ops, log_event, ops_center

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
    sort: str = Query("latest", pattern="^(latest|hot)$"),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """频道列表（公开，含我加入标记）。sort=hot 按热度倒序。"""
    uid = user.id if user else None
    return ok(data=community_service.list_communities(
        db, page, page_size, uid, sort, is_platform_admin=user is not None and user.user_type == 1,
    ))


@router.get("/mine")
def my_communities(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的频道：按 我创建/我管理/我加入 分组返回。"""
    return ok(data=community_service.my_communities(db, user))


@router.get("/{community_id}")
def get_community(
    community_id: int,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """频道详情（含版块列表 + 我的成员身份；平台管理员可查看被封频道）。"""
    community = db.get(Community, community_id)
    if community is None:
        raise NotFoundError("频道不存在")
    uid = user.id if user else None
    return ok(data=community_service.get_community(
        db, community_id, uid, is_platform_admin=user is not None and user.user_type == 1, user=user,
    ))


@router.post("/{community_id}/visit")
def community_visit(
    community_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """访问打点：进入频道工作台/详情时调用，记录 visit 事件（供访问人数/次数统计）。"""
    community = db.get(Community, community_id)
    if community is None:
        raise NotFoundError("频道不存在")
    log_event(db, community.id, user.id, "visit")
    db.commit()
    return ok(message="ok")


@router.get("/{community_id}/ops-center")
def community_ops_center(
    community_id: int,
    board_id: int | None = Query(None, ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """频道运营中心（频道主/有成员数据权限的管理员）：昨日/用户/内容/排名数据。"""
    community = db.get(Community, community_id)
    if community is None:
        raise NotFoundError("频道不存在")
    if not can_view_ops(db, community, user):
        raise PermissionError_("需要频道主或成员管理权限")
    return ok(data=ops_center(db, community, board_id))


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


class TransferRequest(BaseModel):
    target_user_id: int = Field(gt=0)


@router.post("/{community_id}/transfer")
def transfer_community(
    community_id: int,
    payload: TransferRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """转让频道主（仅当前 owner）。"""
    community = db.get(Community, community_id)
    if community is None:
        raise NotFoundError("频道不存在")
    return ok(data=community_service.transfer_community(db, community, user, payload.target_user_id),
              message="频道已转让")


class AllMuteRequest(BaseModel):
    hours: int = Field(ge=0, le=720, description="禁言小时数；0 表示解除")


@router.put("/{community_id}/all-mute")
def set_all_mute(
    community_id: int,
    payload: AllMuteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """全员禁言（发帖与评论被禁，点赞不禁）；0 解除。"""
    community = db.get(Community, community_id)
    if community is None:
        raise NotFoundError("频道不存在")
    return ok(data=community_service.set_all_mute(db, community, user, payload.hours),
              message="已全员禁言" if payload.hours else "已解除全员禁言")


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
