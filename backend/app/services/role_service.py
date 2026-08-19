"""身份组业务逻辑：CRUD + 排序权重 + 成员身份分配 + 等级身份。

权重规则（排序即权重）：
- roles.sort 越小越靠前/权重越高；可管理（编辑/删除/分配/移动）排序严格在操作者之后的身份组；
- 频道主（member_type == OWNER）恒可管理一切；
- 默认组（频道主/超级管理员/普通管理员/普通成员）不可删除；频道主身份组不可修改；
- 等级身份（is_level_role）：roles.level 为门槛，成员活跃等级 ≥ level 自动授予（见 level_service）。
"""
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.permissions import (
    ALL_PERMS,
    PERM_MEMBER_MANAGE,
    PERM_ROLE_MANAGE,
    can_manage,
    get_member,
    get_member_weight,
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


def _get_operator(db: Session, community_id: int, user: User) -> Member | None:
    return get_member(db, community_id, user.id)


def _ensure_manageable(db: Session, operator: Member, role: Role, action: str = "操作") -> None:
    """排序约束：只能管理排序严格在操作者之后的身份组（频道主恒可）。"""
    if operator.member_type == MEMBER_OWNER:
        return
    if get_member_weight(db, operator) >= role.sort:
        raise PermissionError_(f"只能{action}排序在你之后的身份组")


def list_roles(db: Session, community_id: int) -> list[RoleOut]:
    """身份组列表（公开，按排序）。"""
    roles = db.execute(
        select(Role).where(Role.community_id == community_id).order_by(Role.sort, Role.id)
    ).scalars().all()
    return [RoleOut.model_validate(r) for r in roles]


def create_role(db: Session, community_id: int, user: User, payload: CreateRoleRequest) -> RoleOut:
    """创建身份组（role_manage）：追加到社区末尾（sort = 最大 + 1），随后可用 move 调整位置。"""
    operator = require_perms(db, community_id, user, PERM_ROLE_MANAGE)
    _validate_perms(payload.perms)
    max_sort = db.execute(
        select(func.max(Role.sort)).where(Role.community_id == community_id)
    ).scalar() or 0
    role = Role(
        community_id=community_id,
        name=payload.name,
        color=payload.color,
        level=payload.level,
        sort=max_sort + 1,
        perms=payload.perms,
        is_level_role=payload.is_level_role,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    log_op(db, community_id, user.id, "create_role", "role", role.id, {"name": role.name, "sort": role.sort})
    db.commit()
    return RoleOut.model_validate(role)


def update_role(
    db: Session, community_id: int, user: User, role: Role, payload: UpdateRoleRequest
) -> RoleOut:
    """更新身份组（role_manage + 排序约束；频道主身份组不可改；sort 走 move 接口）。"""
    operator = require_perms(db, community_id, user, PERM_ROLE_MANAGE)
    role = _get_role(db, community_id, role.id)
    _ensure_manageable(db, operator, role, "编辑")
    if _used_by_owner(db, role):
        raise ParamError("频道主身份组不可修改")
    data = payload.model_dump(exclude_unset=True)
    data.pop("sort", None)  # 排序只能通过 move 接口调整
    if "perms" in data:
        _validate_perms(data["perms"])
    for field, value in data.items():
        setattr(role, field, value)
    db.commit()
    log_op(db, community_id, user.id, "update_role", "role", role.id, {"name": role.name})
    db.commit()
    return RoleOut.model_validate(role)


def move_role(db: Session, community_id: int, user: User, role: Role, direction: str) -> RoleOut:
    """上移/下移（排序即权重）：与相邻身份组交换 sort；不能把组移到操作者之前。"""
    operator = require_perms(db, community_id, user, PERM_ROLE_MANAGE)
    role = _get_role(db, community_id, role.id)
    _ensure_manageable(db, operator, role, "调整")
    if _used_by_owner(db, role):
        raise ParamError("频道主身份组不可调整位置")

    stmt = select(Role).where(Role.community_id == community_id)
    if direction == "up":
        neighbor = db.execute(
            stmt.where(Role.sort < role.sort).order_by(Role.sort.desc(), Role.id.desc()).limit(1)
        ).scalar_one_or_none()
    else:
        neighbor = db.execute(
            stmt.where(Role.sort > role.sort).order_by(Role.sort.asc(), Role.id.asc()).limit(1)
        ).scalar_one_or_none()
    if neighbor is None:
        raise ParamError("已经在最" + ("前" if direction == "up" else "后"))
    # 上移不能把组插到操作者之前（交换后的新排序位置仍须在操作者之后）
    if (
        direction == "up"
        and operator.member_type != MEMBER_OWNER
        and neighbor.sort <= get_member_weight(db, operator)
    ):
        raise PermissionError_("不能把身份组移到排序在你之前的位置")
    role.sort, neighbor.sort = neighbor.sort, role.sort
    log_op(db, community_id, user.id, "move_role", "role", role.id, {"direction": direction})
    db.commit()
    db.refresh(role)
    return RoleOut.model_validate(role)


def delete_role(db: Session, community_id: int, user: User, role: Role) -> None:
    """删除身份组（role_manage + 排序约束）：默认组与频道主身份组不可删；删除后成员 role_id 清空。"""
    operator = require_perms(db, community_id, user, PERM_ROLE_MANAGE)
    role = _get_role(db, community_id, role.id)
    _ensure_manageable(db, operator, role, "删除")
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
    """成员身份分配（member_manage）：只能分配排序严格在操作者之后的身份组；不能操作同级或更高级成员。

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
        if role.is_default and role.name == "频道主":
            raise PermissionError_("不能分配频道主身份")
        if operator.member_type != MEMBER_OWNER and get_member_weight(db, operator) >= role.sort:
            raise PermissionError_("不能分配排序在你之前或相同的身份组")

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


def my_role(db: Session, community_id: int, user_id: int) -> dict:
    """我的身份组信息（前端控制可编辑范围用）。"""
    member = get_member(db, community_id, user_id)
    if member is None:
        return {"role_id": None, "name": "", "sort": 3, "is_owner": False}
    if member.member_type == MEMBER_OWNER:
        return {"role_id": member.role_id, "name": "频道主", "sort": 0, "is_owner": True}
    if member.role_id:
        role = db.get(Role, member.role_id)
        if role is not None:
            return {"role_id": role.id, "name": role.name, "sort": role.sort, "is_owner": False}
    return {"role_id": None, "name": "", "sort": 3, "is_owner": False}
