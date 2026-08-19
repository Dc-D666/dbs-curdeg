"""身份组业务逻辑（阶段 4）：CRUD + 成员身份分配 + 越级防护。"""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.permissions import (
    ALL_PERMS,
    PERM_MEMBER_MANAGE,
    PERM_ROLE_MANAGE,
    can_manage,
    get_member,
    get_member_level,
    require_perms,
)
from app.core.response import NotFoundError, ParamError, PermissionError_
from app.models.member import MEMBER_OWNER, Member
from app.models.role import Role
from app.models.user import User
from app.schemas.community import (
    AssignRoleRequest,
    CreateRoleRequest,
    MemberOut,
    RoleOut,
    UpdateRoleRequest,
)
from app.services.op_log_service import log_op


def _validate_perms(perms: list[str]) -> None:
    invalid = [p for p in perms if p not in ALL_PERMS]
    if invalid:
        raise ParamError(f"包含非法权限点：{invalid}")


def _get_role(db: Session, community_id: int, role_id: int) -> Role:
    role = db.get(Role, role_id)
    if role is None or role.community_id != community_id:
        raise NotFoundError("身份组不存在")
    return role


def list_roles(db: Session, community_id: int) -> list[RoleOut]:
    """身份组列表（公开，按 level 降序）。"""
    roles = db.execute(
        select(Role).where(Role.community_id == community_id).order_by(Role.level.desc(), Role.id)
    ).scalars().all()
    return [RoleOut.model_validate(r) for r in roles]


def create_role(db: Session, community_id: int, user: User, payload: CreateRoleRequest) -> RoleOut:
    """创建身份组（role_manage）。"""
    require_perms(db, community_id, user, PERM_ROLE_MANAGE)
    _validate_perms(payload.perms)
    role = Role(
        community_id=community_id,
        name=payload.name,
        color=payload.color,
        level=payload.level,
        perms=payload.perms,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    log_op(db, community_id, user.id, "create_role", "role", role.id, {"name": role.name, "level": role.level})
    db.commit()
    return RoleOut.model_validate(role)


def update_role(
    db: Session, community_id: int, user: User, role: Role, payload: UpdateRoleRequest
) -> RoleOut:
    """更新身份组（role_manage；频道主身份组不可改，level 上限 99）。"""
    require_perms(db, community_id, user, PERM_ROLE_MANAGE)
    role = _get_role(db, community_id, role.id)
    if _used_by_owner(db, role):
        raise ParamError("频道主身份组不可修改")
    data = payload.model_dump(exclude_unset=True)
    if "perms" in data:
        _validate_perms(data["perms"])
    for field, value in data.items():
        setattr(role, field, value)
    db.commit()
    log_op(db, community_id, user.id, "update_role", "role", role.id, {"name": role.name})
    db.commit()
    return RoleOut.model_validate(role)


def delete_role(db: Session, community_id: int, user: User, role: Role) -> None:
    """删除身份组（role_manage）：默认组与频道主身份组不可删；删除后成员 role_id 清空。"""
    require_perms(db, community_id, user, PERM_ROLE_MANAGE)
    role = _get_role(db, community_id, role.id)
    if _used_by_owner(db, role):
        raise ParamError("频道主身份组不可删除")
    if role.is_default:
        raise ParamError("默认身份组不可删除")
    db.execute(update(Member).where(Member.role_id == role.id).values(role_id=None))
    log_op(db, community_id, user.id, "delete_role", "role", role.id, {"name": role.name})
    db.delete(role)
    db.commit()


def assign_role(
    db: Session, community_id: int, user: User, target: Member, payload: AssignRoleRequest
) -> MemberOut:
    """成员身份分配（member_manage）：只能分配低于自身 level 的身份组；不能操作同级或更高级成员。

    role_id 为空 → 清除身份（回到 member_type 默认组权限）。
    """
    require_perms(db, community_id, user, PERM_MEMBER_MANAGE)
    operator = get_member(db, community_id, user.id)
    if operator is None or operator.id == target.id:
        raise PermissionError_("不能修改自己的身份")
    if target.member_type == MEMBER_OWNER:
        raise PermissionError_("不能修改频道主的身份")
    if not can_manage(db, operator, target):
        raise PermissionError_("不能管理同级别或更高级别的成员")

    role = None
    if payload.role_id is not None:
        role = _get_role(db, community_id, payload.role_id)
        operator_level = get_member_level(db, operator)
        if role.level >= operator_level:
            raise PermissionError_("不能分配高于或等于自身等级的身份组")

    target.role_id = role.id if role else None
    log_op(
        db, community_id, user.id, "assign_role", "member", target.user_id,
        {"role_id": target.role_id, "role_name": role.name if role else None},
    )
    db.commit()
    db.refresh(target)
    out = MemberOut.model_validate(target)
    out.role_id = target.role_id
    out.role_name = role.name if role else ""
    u = db.get(User, target.user_id)
    if u:
        out.username = u.username
        out.user_nickname = u.nickname or u.username
        out.avatar_url = u.avatar_url
    return out


def _used_by_owner(db: Session, role: Role) -> bool:
    """身份组是否被频道主使用（频道主身份组保护）。"""
    row = db.execute(
        select(Member.id).where(Member.role_id == role.id, Member.member_type == MEMBER_OWNER)
    ).first()
    return row is not None
