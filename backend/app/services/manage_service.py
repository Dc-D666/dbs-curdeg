"""管理动作业务逻辑（阶段 4）：禁言/解除/踢出/拉黑/解除拉黑。

规则：
- 动作前统一 require_perms（shutup/kick/member_manage）；
- 目标必须存在且非频道主；不能操作自己；越级防护（level 必须严格高于目标）；
- 踢出 = 拉黑（is_blocked=True）：成员保留记录，无法发帖、无法重新加入；
- 所有动作写 op_log 留痕。
"""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import (
    PERM_KICK,
    PERM_MEMBER_MANAGE,
    PERM_MODERATE,
    PERM_SHUTUP,
    can_manage,
    require_perms,
)
from app.core.response import NotFoundError, PermissionError_
from app.models.member import MEMBER_OWNER, Member
from app.models.user import User
from app.schemas.community import MemberOut
from app.services.op_log_service import list_ops, log_op


def _require_target(db: Session, community_id: int, user_id: int) -> Member:
    target = db.execute(
        select(Member).where(Member.community_id == community_id, Member.user_id == user_id)
    ).scalar_one_or_none()
    if target is None:
        raise NotFoundError("成员不存在")
    return target


def _guard_target(db: Session, operator: Member, target: Member) -> None:
    """目标保护：不能操作自己/频道主/同级或更高级成员。"""
    if operator.id == target.id:
        raise PermissionError_("不能对自己执行此操作")
    if target.member_type == MEMBER_OWNER:
        raise PermissionError_("不能对频道主执行此操作")
    if not can_manage(db, operator, target):
        raise PermissionError_("不能管理同级别或更高级别的成员")


def _member_out(db: Session, member: Member) -> MemberOut:
    out = MemberOut.model_validate(member)
    u = db.get(User, member.user_id)
    if u:
        out.username = u.username
        out.user_nickname = u.nickname or u.username
        out.avatar_url = u.avatar_url
    return out


def shutup(db: Session, community_id: int, user: User, target_user_id: int, hours: int) -> MemberOut:
    """禁言（shutup 权限）：shutup_expire_at = now + hours。"""
    operator = require_perms(db, community_id, user, PERM_SHUTUP)
    target = _require_target(db, community_id, target_user_id)
    _guard_target(db, operator, target)
    target.shutup_expire_at = datetime.now() + timedelta(hours=hours)
    log_op(db, community_id, user.id, "shutup", "member", target.user_id, {"hours": hours})
    db.commit()
    db.refresh(target)
    return _member_out(db, target)


def unshutup(db: Session, community_id: int, user: User, target_user_id: int) -> MemberOut:
    """解除禁言（shutup 权限）。"""
    operator = require_perms(db, community_id, user, PERM_SHUTUP)
    target = _require_target(db, community_id, target_user_id)
    _guard_target(db, operator, target)
    target.shutup_expire_at = None
    log_op(db, community_id, user.id, "unshutup", "member", target.user_id)
    db.commit()
    db.refresh(target)
    return _member_out(db, target)


def kick(db: Session, community_id: int, user: User, target_user_id: int) -> MemberOut:
    """踢出（kick 权限）：置 is_blocked，无法再发帖与重新加入。"""
    operator = require_perms(db, community_id, user, PERM_KICK)
    target = _require_target(db, community_id, target_user_id)
    _guard_target(db, operator, target)
    target.is_blocked = True
    target.shutup_expire_at = None
    log_op(db, community_id, user.id, "kick", "member", target.user_id)
    db.commit()
    db.refresh(target)
    return _member_out(db, target)


def block(db: Session, community_id: int, user: User, target_user_id: int) -> MemberOut:
    """拉黑（member_manage 权限）：同踢出语义，无法再发帖与重新加入。"""
    operator = require_perms(db, community_id, user, PERM_MEMBER_MANAGE)
    target = _require_target(db, community_id, target_user_id)
    _guard_target(db, operator, target)
    target.is_blocked = True
    target.shutup_expire_at = None
    log_op(db, community_id, user.id, "block", "member", target.user_id)
    db.commit()
    db.refresh(target)
    return _member_out(db, target)


def unblock(db: Session, community_id: int, user: User, target_user_id: int) -> MemberOut:
    """解除拉黑（member_manage 权限）。"""
    operator = require_perms(db, community_id, user, PERM_MEMBER_MANAGE)
    target = _require_target(db, community_id, target_user_id)
    _guard_target(db, operator, target)
    target.is_blocked = False
    log_op(db, community_id, user.id, "unblock", "member", target.user_id)
    db.commit()
    db.refresh(target)
    return _member_out(db, target)


def ops(db: Session, community_id: int, user: User, page: int, page_size: int) -> dict:
    """操作日志列表（moderate 权限）。"""
    require_perms(db, community_id, user, PERM_MODERATE)
    return list_ops(db, community_id, page, page_size)
