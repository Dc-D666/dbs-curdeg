"""权限内核（阶段 4）：成员 → 身份组(roles.perms) → 权限点。

解析规则（按优先级）：
  1. 系统管理员（user.user_type == 1）与频道主（member_type == OWNER）恒拥有全部权限点；
  2. 成员有 role_id 且身份组存在 → 以 roles.perms 为准（自定义身份组可裁剪/扩展权限）；
  3. 成员无身份组（role_id 为空）→ 按 member_type 兜底默认组权限（兼容历史数据/测试）。

越级防护（get_member_level）：管理动作只能作用于 level 严格低于操作者的成员；
频道主 level 100 恒不可被他人管理。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.response import NotFoundError, PermissionError_
from app.models.community import Community
from app.models.member import MEMBER_ADMIN, MEMBER_AI, MEMBER_NORMAL, MEMBER_OWNER, MEMBER_ROBOT, Member
from app.models.role import Role
from app.models.user import User

# ---------- 权限点常量（方案 4.3） ----------

PERM_POST_CREATE = "post.create"
PERM_COMMENT_CREATE = "comment.create"
PERM_TOP = "top"                  # 置顶
PERM_ESSENCE = "essence"          # 加精
PERM_DELETE_POST = "delete_post"  # 删帖（他人）
PERM_DELETE_COMMENT = "delete_comment"  # 删评论（他人）
PERM_SHUTUP = "shutup"            # 禁言
PERM_KICK = "kick"                # 踢人
PERM_MEMBER_MANAGE = "member_manage"  # 成员管理（拉黑/身份分配/审核加入）
PERM_ROLE_MANAGE = "role_manage"  # 身份组管理
PERM_MODERATE = "moderate"        # 内容管理/操作日志
PERM_SUPER = "super"              # 频道主专属

ALL_PERMS = [
    PERM_POST_CREATE, PERM_COMMENT_CREATE, PERM_TOP, PERM_ESSENCE,
    PERM_DELETE_POST, PERM_DELETE_COMMENT, PERM_SHUTUP, PERM_KICK,
    PERM_MEMBER_MANAGE, PERM_ROLE_MANAGE, PERM_MODERATE, PERM_SUPER,
]

PERMS_OWNER = list(ALL_PERMS)
PERMS_ADMIN = [
    PERM_POST_CREATE, PERM_COMMENT_CREATE, PERM_TOP, PERM_ESSENCE,
    PERM_DELETE_POST, PERM_DELETE_COMMENT, PERM_SHUTUP, PERM_KICK,
    PERM_MEMBER_MANAGE, PERM_MODERATE,
]
PERMS_NORMAL = [PERM_POST_CREATE, PERM_COMMENT_CREATE]

# member_type 无身份组时的兜底（兼容老数据）
_DEFAULT_PERMS: dict[int, list[str]] = {
    MEMBER_OWNER: PERMS_OWNER,
    MEMBER_ADMIN: PERMS_ADMIN,
    MEMBER_NORMAL: PERMS_NORMAL,
    MEMBER_ROBOT: PERMS_NORMAL,
    MEMBER_AI: PERMS_NORMAL,
}

# 默认 level 权重（无身份组时按 member_type 估算，用于越级防护）
_DEFAULT_LEVEL: dict[int, int] = {
    MEMBER_OWNER: 100,
    MEMBER_ADMIN: 50,
    MEMBER_NORMAL: 10,
    MEMBER_ROBOT: 10,
    MEMBER_AI: 10,
}


def get_member(db: Session, community_id: int, user_id: int) -> Member | None:
    """查询频道成员记录（含被拉黑成员）。"""
    return db.execute(
        select(Member).where(Member.community_id == community_id, Member.user_id == user_id)
    ).scalar_one_or_none()


def get_member_perms(db: Session, community_id: int, user: User) -> set[str]:
    """解析用户在某频道的权限点集合。"""
    if user.user_type == 1:  # 系统管理员
        return set(ALL_PERMS)
    member = get_member(db, community_id, user.id)
    if member is None or member.is_blocked:
        return set()
    if member.member_type == MEMBER_OWNER:
        return set(ALL_PERMS)
    if member.role_id:
        role = db.get(Role, member.role_id)
        if role is not None:
            return set(role.perms or [])
    return set(_DEFAULT_PERMS.get(member.member_type, PERMS_NORMAL))


def get_member_level(db: Session, member: Member) -> int:
    """成员 level 权重：有身份组用 role.level，否则按 member_type 兜底。"""
    if member.member_type == MEMBER_OWNER:
        return _DEFAULT_LEVEL[MEMBER_OWNER]
    if member.role_id:
        role = db.get(Role, member.role_id)
        if role is not None:
            return role.level
    return _DEFAULT_LEVEL.get(member.member_type, 10)


def can_manage(db: Session, operator: Member, target: Member) -> bool:
    """越级防护：操作者 level 必须严格高于目标（owner 恒 100，不可被管理）。"""
    return get_member_level(db, operator) > get_member_level(db, target)


def require_perms(db: Session, community_id: int, user: User, *perms: str) -> Member | None:
    """校验用户对指定频道拥有全部权限点；不满足抛 1002，返回成员记录（系统管理员可能非成员，返回 None）。"""
    community = db.get(Community, community_id)
    if community is None or community.status != 0:
        raise NotFoundError("频道不存在")
    if user.user_type == 1:  # 系统管理员：全量权限，不要求是频道成员
        return None
    member = get_member(db, community_id, user.id)
    if member is None or member.is_blocked:
        raise PermissionError_("只有频道成员可以执行此操作")
    if member.member_type == MEMBER_OWNER:
        return member
    if member.role_id:
        role = db.get(Role, member.role_id)
        if role is not None:
            member_perms = set(role.perms or [])
        else:
            member_perms = set(_DEFAULT_PERMS.get(member.member_type, PERMS_NORMAL))
    else:
        member_perms = set(_DEFAULT_PERMS.get(member.member_type, PERMS_NORMAL))
    missing = [p for p in perms if p not in member_perms]
    if missing:
        raise PermissionError_("无权限执行该操作")
    return member
