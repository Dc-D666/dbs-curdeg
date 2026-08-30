"""活跃等级（阶段 4）：互动加分 + 等级身份自动授予/回收。

- members.level 默认 1；发帖 +5 / 评论 +2 / 点赞 +1（常量可调）
- 等级身份（roles.is_level_role）：成员活跃等级 ≥ role.level 自动授予，掉级自动回收
- 手动分配的身份（排序更靠前）优先，不被等级身份覆盖；等级身份之间取门槛最高者
- 加分与授予在同一事务内，由调用方 commit
"""
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.member import Member
from app.models.role import Role

LEVEL_POINTS = {"post": 5, "comment": 2, "like": 1}


def add_level(db: Session, community_id: int, user_id: int, points: int) -> Member | None:
    """给成员加活跃等级分，并触发等级身份自动授予/回收；返回成员（未加成功返回 None）。"""
    member = db.execute(
        select(Member).where(Member.community_id == community_id, Member.user_id == user_id)
    ).scalar_one_or_none()
    if member is None or member.is_blocked:
        return None
    # 原子加分（并发互动防丢分）+ 顺带激活 last_active_at（原为死列，08-29 整改）
    db.execute(
        update(Member)
        .where(Member.id == member.id)
        .values(level=func.greatest(1, Member.level + points), last_active_at=func.now())
    )
    db.refresh(member)
    _sync_level_role(db, member)
    return member


def _sync_level_role(db: Session, member: Member) -> None:
    """等级身份同步（不 commit，由调用方事务统一提交）。"""
    level_roles = db.execute(
        select(Role).where(Role.community_id == member.community_id, Role.is_level_role.is_(True))
    ).scalars().all()
    if not level_roles:
        return

    eligible = [r for r in level_roles if member.level >= r.level]
    if eligible:
        # 达标：取门槛最高的等级身份；手动分配的身份（排序更靠前）优先，不被覆盖
        target = max(eligible, key=lambda r: (r.level, -r.sort))
        if member.role_id != target.id:
            cur = db.get(Role, member.role_id) if member.role_id else None
            if cur is None or (cur.sort, cur.id) > (target.sort, target.id):
                member.role_id = target.id
    else:
        # 掉级回收：当前身份是等级身份且不达标 → 清除
        cur = db.get(Role, member.role_id) if member.role_id else None
        if cur is not None and cur.is_level_role and member.level < cur.level:
            member.role_id = None
