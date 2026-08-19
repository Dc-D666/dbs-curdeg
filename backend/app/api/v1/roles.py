"""身份组接口（阶段 4）：CRUD / 权限点配置 / 成员身份分配。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import NotFoundError, ok
from app.db import get_db
from app.models.community import Community
from app.models.member import Member
from app.models.role import Role
from app.models.user import User
from app.schemas.community import AssignRoleRequest, CreateRoleRequest, MoveRoleRequest, UpdateRoleRequest
from app.services import role_service

router = APIRouter(prefix="/communities/{community_id}", tags=["roles"])


def _get_community(db: Session, community_id: int) -> Community:
    community = db.get(Community, community_id)
    if community is None or community.status != 0:
        raise NotFoundError("频道不存在")
    return community


@router.get("/roles/my")
def my_role(
    community_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的身份组信息（可编辑范围判断）。注意：须声明在 /roles/{role_id} 之前。"""
    _get_community(db, community_id)
    return ok(data=role_service.my_role(db, community_id, user.id))


@router.get("/roles")
def list_roles(
    community_id: int,
    db: Session = Depends(get_db),
):
    """身份组列表（公开，渲染成员身份标识用）。"""
    _get_community(db, community_id)
    return ok(data=role_service.list_roles(db, community_id))


@router.post("/roles")
def create_role(
    community_id: int,
    payload: CreateRoleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建身份组（role_manage）。"""
    _get_community(db, community_id)
    return ok(data=role_service.create_role(db, community_id, user, payload), message="身份组已创建")


@router.put("/roles/{role_id}")
def update_role(
    community_id: int,
    role_id: int,
    payload: UpdateRoleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新身份组（role_manage；频道主身份组不可改）。"""
    _get_community(db, community_id)
    return ok(data=role_service.update_role(db, community_id, user, db.get(Role, role_id), payload), message="已保存")


@router.post("/roles/{role_id}/move")
def move_role(
    community_id: int,
    role_id: int,
    payload: MoveRoleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上移/下移身份组（排序即权重，role_manage + 排序约束）。"""
    _get_community(db, community_id)
    return ok(data=role_service.move_role(db, community_id, user, db.get(Role, role_id), payload.direction), message="已调整")


@router.delete("/roles/{role_id}")
def delete_role(
    community_id: int,
    role_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除身份组（role_manage；默认组不可删，删除后成员身份清空）。"""
    _get_community(db, community_id)
    role_service.delete_role(db, community_id, user, db.get(Role, role_id))
    return ok(message="身份组已删除")


@router.post("/members/{user_id}/role")
def assign_role(
    community_id: int,
    user_id: int,
    payload: AssignRoleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """成员身份分配（member_manage；越级防护：只能分配低于自身 level 的身份组）。"""
    _get_community(db, community_id)
    target = db.execute(
        select(Member).where(Member.community_id == community_id, Member.user_id == user_id)
    ).scalar_one_or_none()
    if target is None:
        raise NotFoundError("成员不存在")
    return ok(data=role_service.assign_role(db, community_id, user, target, payload), message="身份已更新")
