"""权限内核（阶段 4）：成员 → 身份组(roles.perms) → 权限点。

解析规则（按优先级）：
  1. 频道主（member_type == OWNER）恒拥有全部权限点；
  2. 成员有 role_id 且身份组存在 → 以 roles.perms 为准（自定义身份组可裁剪/扩展权限）；
  3. 成员无身份组（role_id 为空）→ 按 member_type 兜底默认组权限（兼容历史数据/测试）。

系统管理员（user_type == 1）定位是**平台级**巡视者：只保留跨频道的系统级能力
（封禁/解封频道、封禁/解封用户、运营看板等，各接口自行判 user_type），
**不再自动获得任何频道级权限点**（删帖/删评论/置顶/禁言/踢人等须由频道自身授权）。
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
# 超级管理员：全量 - super（频道主专属）；不能解散频道（解散走 member_type==OWNER 检查）
PERMS_SUPER_ADMIN = [p for p in ALL_PERMS if p != PERM_SUPER]
PERMS_NORMAL = [PERM_POST_CREATE, PERM_COMMENT_CREATE]

# member_type 无身份组时的兜底（兼容老数据）
_DEFAULT_PERMS: dict[int, list[str]] = {
    MEMBER_OWNER: PERMS_OWNER,
    MEMBER_ADMIN: PERMS_ADMIN,
    MEMBER_NORMAL: PERMS_NORMAL,
    MEMBER_ROBOT: PERMS_NORMAL,
    MEMBER_AI: PERMS_NORMAL,
}

# 默认 sort 权重（无身份组时按 member_type 兜底；sort 越小权重越高，可管理排序在后的组）
_DEFAULT_SORT: dict[int, int] = {
    MEMBER_OWNER: 0,
    MEMBER_ADMIN: 2,
    MEMBER_NORMAL: 3,
    MEMBER_ROBOT: 3,
    MEMBER_AI: 3,
}


def get_member(db: Session, community_id: int, user_id: int) -> Member | None:
    """查询频道成员记录（含被拉黑成员）。"""
    return db.execute(
        select(Member).where(Member.community_id == community_id, Member.user_id == user_id)
    ).scalar_one_or_none()


def get_member_perms(db: Session, community_id: int, user: User) -> set[str]:
    """解析用户在某频道的权限点集合。

    系统管理员不在此放行：频道级权限须由频道自身（频道主/身份组）授予，
    平台管理员只有各系统级接口单独判 user_type 的能力。
    """
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


def get_member_weight(db: Session, member: Member) -> int:
    """成员权重 = 身份组 sort（越小越靠前/权重越高，可管理排序在后的组）。

    频道主恒 0（最前）；无身份组按 member_type 兜底（admin=2 对齐普通管理员、normal=3 对齐普通成员）。
    """
    if member.member_type == MEMBER_OWNER:
        return 0
    if member.role_id:
        role = db.get(Role, member.role_id)
        if role is not None:
            return role.sort
    return _DEFAULT_SORT.get(member.member_type, 3)


def can_manage(db: Session, operator: Member, target: Member) -> bool:
    """越级防护：操作者权重必须严格高于目标（sort 更小）；频道主（0）恒不可被管理。"""
    return get_member_weight(db, operator) < get_member_weight(db, target)


def require_perms(db: Session, community_id: int, user: User, *perms: str) -> Member | None:
    """校验用户对指定频道拥有全部权限点；不满足抛 1002，返回成员记录。

    系统管理员不再放行（09-01 定位重设）：频道级操作（删帖/置顶/禁言…）
    必须是频道成员且被授权；平台级能力（封频道/封用户）走各自接口的 user_type 判断。
    """
    community = db.get(Community, community_id)
    if community is None or community.status != 0:
        raise NotFoundError("频道不存在")
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
