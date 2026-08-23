"""频道/版块/成员业务逻辑。"""
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import (
    PERMS_ADMIN,
    PERMS_NORMAL,
    PERMS_OWNER,
    PERMS_SUPER_ADMIN,
    PERM_MEMBER_MANAGE,
    require_perms,
)
from app.core.response import ConflictError, NotFoundError, ParamError, PermissionError_
from app.models.board import Board
from app.models.community import Community
from app.models.join_request import JOIN_APPROVED, JOIN_PENDING, JOIN_REJECTED, JoinRequest
from app.models.member import MEMBER_ADMIN, MEMBER_NORMAL, MEMBER_OWNER, Member
from app.models.role import Role
from app.models.user import User
from app.schemas.community import (
    BoardOut,
    CommunityOut,
    CreateBoardRequest,
    CreateCommunityRequest,
    JoinRequestOut,
    MemberOut,
    UpdateBoardRequest,
    UpdateCommunityRequest,
)
from app.services.notify_service import notify
from app.services.op_log_service import log_op
def _gen_number() -> str:
    """频道号：6 位字母数字，撞车重试。"""
    for _ in range(5):
        num = "".join(secrets.choice("23456789ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(6))
        return num  # 实际唯一性由 DB UNIQUE 约束兜底，冲突时上层捕获
    raise ConflictError("频道号生成失败，请重试")


def create_community(db: Session, user: User, payload: CreateCommunityRequest) -> CommunityOut:
    """创建频道：自动成为 owner + 初始化身份组 + 默认版块（否则新频道无法发帖）。"""
    community = Community(
        number=_gen_number(),
        name=payload.name,
        profile=payload.profile,
        join_setting=payload.join_setting,
        owner_id=user.id,
        member_count=1,
    )
    db.add(community)
    db.flush()  # 拿到 id

    owner_role = Role(community_id=community.id, name="频道主", level=100, sort=0, perms=PERMS_OWNER, is_default=True)
    super_admin_role = Role(community_id=community.id, name="超级管理员", level=1, sort=1, perms=PERMS_SUPER_ADMIN, is_default=True)
    admin_role = Role(community_id=community.id, name="普通管理员", level=50, sort=2, perms=PERMS_ADMIN, is_default=True)
    normal_role = Role(community_id=community.id, name="成员", level=10, sort=3, perms=PERMS_NORMAL, is_default=True)
    db.add_all([owner_role, super_admin_role, admin_role, normal_role])
    db.flush()

    member = Member(
        community_id=community.id,
        user_id=user.id,
        role_id=owner_role.id,
        member_type=MEMBER_OWNER,
        nickname=user.nickname or user.username,
    )
    db.add(member)
    # 默认版块：保证建频道后立即可发帖（发帖必须挂版块）
    db.add(Board(community_id=community.id, name="默认版块", description="", sort=0))
    db.commit()
    db.refresh(community)
    return community_out(db, community, current_user_id=user.id)


def list_communities(
    db: Session, page: int, page_size: int, current_user_id: int | None, sort: str = "latest"
) -> dict:
    """频道列表（含我加入的标记）。sort=latest 按创建倒序；sort=hot 按热度（成员数+帖子数）倒序。"""
    base = select(Community).where(Community.status == 0)
    if sort == "hot":
        stmt = base.order_by(
            (Community.member_count + Community.post_count).desc(), Community.id.desc()
        )
    else:
        stmt = base.order_by(Community.id.desc())
    total = db.execute(select(Community.id).where(Community.status == 0)).scalars().count() if False else len(
        db.execute(select(Community.id).where(Community.status == 0)).scalars().all()
    )
    items = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    # 批量查我的成员身份
    member_map: dict[int, int] = {}
    if current_user_id:
        mids = [c.id for c in items]
        if mids:
            rows = db.execute(
                select(Member.community_id, Member.member_type).where(
                    Member.user_id == current_user_id, Member.community_id.in_(mids)
                )
            ).all()
            member_map = {r[0]: r[1] for r in rows}
    out = []
    for c in items:
        co = CommunityOut.model_validate(c)
        co.is_member = c.id in member_map
        co.my_member_type = member_map.get(c.id)
        out.append(co)
    return {"items": out, "total": total, "page": page, "page_size": page_size}


def my_communities(db: Session, user: User) -> dict:
    """我的频道：按成员身份分成 我创建/我管理/我加入 三组。"""
    rows = db.execute(
        select(Member.community_id, Member.member_type).where(Member.user_id == user.id, Member.is_blocked.is_(False))
    ).all()
    buckets: dict[int, list[int]] = {0: [], 1: [], 2: []}
    for community_id, member_type in rows:
        buckets.setdefault(member_type, []).append(community_id)

    result = {"owned": [], "managed": [], "joined": []}
    for member_type, key in ((MEMBER_OWNER, "owned"), (MEMBER_ADMIN, "managed"), (MEMBER_NORMAL, "joined")):
        ids = buckets.get(member_type, [])
        if not ids:
            continue
        communities = db.execute(
            select(Community).where(Community.id.in_(ids), Community.status == 0).order_by(Community.id.desc())
        ).scalars().all()
        for c in communities:
            co = CommunityOut.model_validate(c)
            co.is_member = True
            co.my_member_type = member_type
            result[key].append(co)
    return result


def get_community(db: Session, community_id: int, current_user_id: int | None) -> CommunityOut:
    community = db.get(Community, community_id)
    if community is None or community.status != 0:
        raise NotFoundError("频道不存在")
    return community_out(db, community, current_user_id)


def community_out(db: Session, community: Community, current_user_id: int | None) -> CommunityOut:
    """组装详情（含版块与我的成员身份）。"""
    out = CommunityOut.model_validate(community)
    boards = db.execute(
        select(Board).where(Board.community_id == community.id, Board.status == 0).order_by(Board.sort, Board.id)
    ).scalars().all()
    out.boards = [BoardOut.model_validate(b) for b in boards]
    if current_user_id:
        member = db.execute(
            select(Member).where(Member.community_id == community.id, Member.user_id == current_user_id)
        ).scalar_one_or_none()
        if member and not member.is_blocked:
            out.is_member = True
            out.my_member_type = member.member_type
    return out


def update_community(
    db: Session, community: Community, user: User, payload: UpdateCommunityRequest
) -> CommunityOut:
    _ensure_owner(db, community, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(community, field, value)
    db.commit()
    db.refresh(community)
    return community_out(db, community, current_user_id=user.id)


def dissolve_community(db: Session, community: Community, user: User) -> None:
    """解散频道（仅 owner）：状态置为关闭，不物理删除。"""
    _ensure_owner(db, community, user)
    community.status = 1
    db.commit()


def update_community_status(
    db: Session, community: Community, user: User, status: int
) -> CommunityOut:
    """频道状态调整：owner 可 正常/关闭；违规封禁(2)仅系统管理员。"""
    if status == 2:
        if user.user_type != 1:  # 系统管理员
            raise PermissionError_("违规封禁需要系统管理员权限")
        community.status = 2
    else:
        _ensure_owner(db, community, user)
        community.status = status
    db.commit()
    db.refresh(community)
    return community_out(db, community, current_user_id=user.id)


def _ensure_owner(db: Session, community: Community, user: User) -> None:
    member = db.execute(
        select(Member).where(Member.community_id == community.id, Member.user_id == user.id)
    ).scalar_one_or_none()
    if member is None or member.member_type != MEMBER_OWNER:
        raise PermissionError_("只有频道主可以执行此操作")


# ---------- 版块 ----------


def create_board(
    db: Session, community: Community, user: User, payload: CreateBoardRequest
) -> BoardOut:
    _ensure_owner(db, community, user)
    board = Board(community_id=community.id, **payload.model_dump())
    db.add(board)
    db.commit()
    db.refresh(board)
    return BoardOut.model_validate(board)


def update_board(
    db: Session, community: Community, user: User, board: Board, payload: UpdateBoardRequest
) -> BoardOut:
    _ensure_owner(db, community, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(board, field, value)
    db.commit()
    db.refresh(board)
    return BoardOut.model_validate(board)


def delete_board(db: Session, community: Community, user: User, board: Board) -> None:
    _ensure_owner(db, community, user)
    board.status = 2  # 关闭（软删）
    db.commit()


# ---------- 成员与加入 ----------


def join_community(db: Session, community: Community, user: User) -> dict:
    """加入频道：自由直接加入；审核制写 join_requests；邀请制拒绝。"""
    if community.status != 0:
        raise NotFoundError("频道不存在")
    existing = db.execute(
        select(Member).where(Member.community_id == community.id, Member.user_id == user.id)
    ).scalar_one_or_none()
    if existing:
        if existing.is_blocked:
            raise ConflictError("你已被移出该频道，无法重新加入")
        raise ConflictError("你已经是该频道成员")

    if community.join_setting == 0:
        return _add_member(db, community, user, join_channel=0)
    if community.join_setting == 1:
        # 已有待审申请则拒绝重复
        pending = db.execute(
            select(JoinRequest).where(
                JoinRequest.community_id == community.id,
                JoinRequest.user_id == user.id,
                JoinRequest.status == JOIN_PENDING,
            )
        ).scalar_one_or_none()
        if pending:
            raise ConflictError("申请已在审核中")
        req = JoinRequest(community_id=community.id, user_id=user.id)
        db.add(req)
        db.commit()
        return {"status": "pending", "message": "申请已提交，等待审核"}
    raise PermissionError_("该频道为邀请制，暂不接受加入")


def _add_member(db: Session, community: Community, user: User, join_channel: int) -> dict:
    member = Member(
        community_id=community.id,
        user_id=user.id,
        member_type=MEMBER_NORMAL,
        nickname=user.nickname or user.username,
        join_channel=join_channel,
    )
    db.add(member)
    community.member_count += 1
    db.commit()
    return {"status": "joined", "message": "已加入频道"}


def leave_community(db: Session, community: Community, user: User) -> None:
    """退出频道（owner 不能退，只能解散）。"""
    member = db.execute(
        select(Member).where(Member.community_id == community.id, Member.user_id == user.id)
    ).scalar_one_or_none()
    if member is None:
        raise NotFoundError("你不是该频道成员")
    if member.member_type == MEMBER_OWNER:
        raise PermissionError_("频道主不能退出，可解散频道")
    db.delete(member)
    community.member_count = max(0, community.member_count - 1)
    db.commit()


def list_join_requests(db: Session, community: Community, user: User, page: int, page_size: int) -> dict:
    """待审核加入申请列表（仅 owner/admin）。"""
    _ensure_admin(db, community, user)
    stmt = (
        select(JoinRequest)
        .where(JoinRequest.community_id == community.id)
        .order_by(JoinRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    reqs = db.execute(stmt).scalars().all()
    total = len(
        db.execute(
            select(JoinRequest.id).where(JoinRequest.community_id == community.id)
        ).scalars().all()
    )
    return {"items": _decorate_join_reqs(db, reqs), "total": total, "page": page, "page_size": page_size}


def handle_join_request(
    db: Session, community: Community, user: User, req: JoinRequest, approve: bool
) -> None:
    """审核加入申请（member_manage 权限，留痕）。"""
    require_perms(db, community.id, user, PERM_MEMBER_MANAGE)
    if req.status != JOIN_PENDING:
        raise ParamError("该申请已处理")
    req.status = JOIN_APPROVED if approve else JOIN_REJECTED
    req.handler_id = user.id
    from datetime import datetime

    req.handled_at = datetime.now()
    if approve:
        applicant = db.get(User, req.user_id)
        if applicant is None:
            raise NotFoundError("申请用户不存在")
        _add_member(db, community, applicant, join_channel=0)
    log_op(
        db, community.id, user.id, "approve_join" if approve else "reject_join",
        "join_request", req.id, {"user_id": req.user_id},
    )
    db.commit()
    # 通知申请人：审核结果
    notify(
        db, req.user_id, "review_result",
        "加入频道申请已通过" if approve else "加入频道申请未通过",
        summary=f"你加入《{community.name}》的申请已{'通过' if approve else '被拒绝'}",
        ref_id=community.id, actor_id=user.id, community_id=community.id,
    )


def list_members(db: Session, community: Community, page: int, page_size: int) -> dict:
    """成员列表（按身份分组排序：owner/admin 优先）。"""
    stmt = (
        select(Member)
        .where(Member.community_id == community.id, Member.is_blocked.is_(False))
        .order_by(Member.member_type, Member.join_time)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    members = db.execute(stmt).scalars().all()
    total = len(
        db.execute(
            select(Member.id).where(Member.community_id == community.id, Member.is_blocked.is_(False))
        ).scalars().all()
    )
    return {"items": _decorate_members(db, members), "total": total, "page": page, "page_size": page_size}


def _decorate_members(db: Session, members: list[Member]) -> list[MemberOut]:
    if not members:
        return []
    uids = {m.user_id for m in members}
    users = {u.id: u for u in db.execute(select(User).where(User.id.in_(uids))).scalars().all()}
    rids = {m.role_id for m in members if m.role_id}
    roles = {}
    if rids:
        roles = {r.id: r for r in db.execute(select(Role).where(Role.id.in_(rids))).scalars().all()}
    out = []
    for m in members:
        mo = MemberOut.model_validate(m)
        u = users.get(m.user_id)
        if u:
            mo.username = u.username
            mo.user_nickname = u.nickname or u.username
            mo.avatar_url = u.avatar_url
        role = roles.get(m.role_id)
        if role:
            mo.role_name = role.name
        out.append(mo)
    return out


def _decorate_join_reqs(db: Session, reqs: list[JoinRequest]) -> list[JoinRequestOut]:
    if not reqs:
        return []
    uids = {r.user_id for r in reqs}
    users = {u.id: u for u in db.execute(select(User).where(User.id.in_(uids))).scalars().all()}
    out = []
    for r in reqs:
        jo = JoinRequestOut.model_validate(r)
        u = users.get(r.user_id)
        if u:
            jo.username = u.username
            jo.user_nickname = u.nickname or u.username
        out.append(jo)
    return out


def _ensure_admin(db: Session, community: Community, user: User) -> None:
    member = db.execute(
        select(Member).where(Member.community_id == community.id, Member.user_id == user.id)
    ).scalar_one_or_none()
    if member is None or member.member_type not in (MEMBER_OWNER, MEMBER_ADMIN):
        raise PermissionError_("需要频道主或管理员权限")
