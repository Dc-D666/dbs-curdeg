"""频道/版块/成员业务逻辑。"""
import secrets
from datetime import datetime, timedelta

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.permissions import (
    PERMS_ADMIN,
    PERMS_NORMAL,
    PERMS_OWNER,
    PERMS_SUPER_ADMIN,
    PERM_MEMBER_MANAGE,
    get_member_perms,
    require_perms,
)
from app.core.response import ConflictError, NotFoundError, ParamError, PermissionError_
from app.models.board import Board
from app.models.board_role_perm import BoardRolePerm
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
from app.services.ops_service import log_event


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
    db: Session, page: int, page_size: int, current_user_id: int | None, sort: str = "latest",
    is_platform_admin: bool = False,
) -> dict:
    """频道列表（含我加入的标记）。sort=latest 按创建倒序；sort=hot 按热度（成员数+帖子数）倒序。"""
    base = select(Community).where(Community.status == 0)
    if sort == "hot":
        stmt = base.order_by(
            (Community.member_count + Community.post_count).desc(), Community.id.desc()
        )
    else:
        stmt = base.order_by(Community.id.desc())
    total = len(db.execute(select(Community.id).where(Community.status == 0)).scalars().all())
    items = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    # 批量查我的成员身份（被拉黑的行不算"已加入"，与 my_communities 口径一致）
    member_map: dict[int, int] = {}
    if current_user_id:
        mids = [c.id for c in items]
        if mids:
            rows = db.execute(
                select(Member.community_id, Member.member_type).where(
                    Member.user_id == current_user_id,
                    Member.community_id.in_(mids),
                    Member.is_blocked.is_(False),
                )
            ).all()
            member_map = {r[0]: r[1] for r in rows}
    out = []
    for c in items:
        co = CommunityOut.model_validate(c)
        co.is_member = c.id in member_map
        co.my_member_type = member_map.get(c.id)
        co.is_platform_admin = is_platform_admin
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


def get_community(
    db: Session, community_id: int, current_user_id: int | None, is_platform_admin: bool = False,
    user: User | None = None,
) -> CommunityOut:
    community = db.get(Community, community_id)
    # 平台管理员可查看被封禁频道（巡视 + 解封入口）；普通用户/游客只见活跃频道
    if community is None or (community.status != 0 and not is_platform_admin):
        raise NotFoundError("频道不存在")
    return community_out(db, community, current_user_id, is_platform_admin, user)


def community_out(
    db: Session, community: Community, current_user_id: int | None, is_platform_admin: bool = False,
    user: User | None = None,
) -> CommunityOut:
    """组装详情（含版块与我的成员身份 / 权限点）。"""
    out = CommunityOut.model_validate(community)
    out.is_platform_admin = is_platform_admin
    boards = db.execute(
        select(Board).where(Board.community_id == community.id, Board.status == 0).order_by(Board.sort, Board.id)
    ).scalars().all()
    out.boards = [BoardOut.model_validate(b) for b in boards]
    # 版块发帖白名单批量聚合（一次 IN 查询）
    if boards:
        role_map: dict[int, list[int]] = {}
        for brp in db.execute(
            select(BoardRolePerm).where(BoardRolePerm.board_id.in_([b.id for b in boards]))
        ).scalars().all():
            role_map.setdefault(brp.board_id, []).append(brp.role_id)
        for o in out.boards:
            o.allow_post_role_ids = sorted(role_map.get(o.id, []))
    if current_user_id:
        member = db.execute(
            select(Member).where(Member.community_id == community.id, Member.user_id == current_user_id)
        ).scalar_one_or_none()
        if member and not member.is_blocked:
            out.is_member = True
            out.my_member_type = member.member_type
            out.is_owner = member.member_type == MEMBER_OWNER
    # 权限点：供前端按权限显示「管理中心/运营中心」等频道级管理入口
    if current_user_id:
        if user is None:
            user = db.get(User, current_user_id)
        if user is not None:
            out.my_perms = sorted(get_member_perms(db, community.id, user))
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
    """频道状态调整：owner 可 正常/关闭；违规封禁(2)与解封(2→0)为系统管理员专属。

    系统管理员封禁/解封频道时，向频道全体成员发送系统通知（供 /notifications 系统通知查看）。
    """
    if status == 2:
        if user.user_type != 1:  # 系统管理员
            raise PermissionError_("违规封禁需要系统管理员权限")
        community.status = 2
        _notify_all_members(db, community.id, "你的频道已被封禁",
                            f"频道《{community.name}》已被平台封禁，内容保留但全体用户无法访问。")
    elif community.status == 2 and status == 0:
        # 解封：被系统管理员封禁(2)的频道，只有系统管理员能恢复；
        # owner 此时无权（避免被封频道主自行解除封禁）
        if user.user_type != 1:
            raise PermissionError_("解除违规封禁需要系统管理员权限")
        community.status = 0
        _notify_all_members(db, community.id, "你加入的频道已解封",
                            f"频道《{community.name}》已恢复对外可见。")
    else:
        _ensure_owner(db, community, user)
        community.status = status
    db.commit()
    db.refresh(community)
    return community_out(db, community, current_user_id=user.id, is_platform_admin=user.user_type == 1)


def _notify_all_members(db: Session, community_id: int, title: str, summary: str) -> None:
    """向频道全体成员（非拉黑）发送系统通知。仅当频道被封禁/解封等系统级动作时调用。"""
    rows = db.execute(
        select(Member.user_id).where(
            Member.community_id == community_id, Member.is_blocked.is_(False)
        )
    ).scalars().all()
    for uid in rows:
        notify(db, uid, "system", title, summary, ref_id=community_id,
               ref_type="community", community_id=community_id)


def transfer_community(db: Session, community: Community, user: User, target_user_id: int) -> CommunityOut:
    """转让频道主：仅当前 owner 可操作，目标须为未被拉黑的成员且非自己。

    转让后：目标成员 member_type=0（频道主）、role_id 置空；原 owner 降为普通成员(2)。
    """
    _ensure_owner(db, community, user)
    if target_user_id == user.id:
        raise ParamError("不能转让给频道主自己")
    target = db.execute(
        select(Member).where(
            Member.community_id == community.id, Member.user_id == target_user_id
        )
    ).scalar_one_or_none()
    if target is None:
        raise NotFoundError("目标用户不是该频道成员")
    if target.is_blocked:
        raise ParamError("不能转让给已被移出的成员")

    owner = db.execute(
        select(Member).where(
            Member.community_id == community.id, Member.user_id == user.id
        )
    ).scalar_one_or_none()
    if owner is not None:
        owner.member_type = MEMBER_NORMAL
        owner.role_id = None
    target.member_type = MEMBER_OWNER
    target.role_id = None
    community.owner_id = target_user_id
    db.commit()
    db.refresh(community)
    return community_out(db, community, current_user_id=user.id)


def set_all_mute(db: Session, community: Community, user: User, hours: int) -> CommunityOut:
    """全员禁言（频道主/有 member_manage 权限）：禁言 N 小时（1-720，0 表示解除）。

    发帖与评论被禁，点赞不禁（发帖/评论路径校验 all_muted_until）。
    """
    from app.core.permissions import PERM_MEMBER_MANAGE, require_perms

    require_perms(db, community.id, user, PERM_MEMBER_MANAGE)
    if hours < 0 or hours > 720:
        raise ParamError("禁言时长需在 0-720 小时之间")
    if hours == 0:
        community.all_muted_until = None
    else:
        community.all_muted_until = datetime.now() + timedelta(hours=hours)
    db.commit()
    db.refresh(community)
    return community_out(db, community, current_user_id=user.id, is_platform_admin=user.user_type == 1)


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
    data = payload.model_dump()
    role_ids = data.pop("allow_post_role_ids", [])
    board = Board(community_id=community.id, **data)
    db.add(board)
    db.flush()  # 取 board.id：白名单写规范化后的 board_role_perms 关系表
    for rid in role_ids:
        db.add(BoardRolePerm(board_id=board.id, role_id=rid))
    db.commit()
    db.refresh(board)
    return _board_out(db, board)


def update_board(
    db: Session, community: Community, user: User, board: Board, payload: UpdateBoardRequest
) -> BoardOut:
    _ensure_owner(db, community, user)
    data = payload.model_dump(exclude_unset=True)
    role_ids = data.pop("allow_post_role_ids", None)
    for field, value in data.items():
        setattr(board, field, value)
    if role_ids is not None:
        # 全量替换白名单行（关系表规范化写法）
        db.execute(delete(BoardRolePerm).where(BoardRolePerm.board_id == board.id))
        for rid in role_ids:
            db.add(BoardRolePerm(board_id=board.id, role_id=rid))
    db.commit()
    db.refresh(board)
    return _board_out(db, board)


def _board_out(db: Session, board: Board) -> BoardOut:
    """版块输出：发帖白名单从 board_role_perms 关系表聚合（保持 API 形状不变）。"""
    out = BoardOut.model_validate(board)
    out.allow_post_role_ids = sorted(
        db.execute(select(BoardRolePerm.role_id).where(BoardRolePerm.board_id == board.id)).scalars().all()
    )
    return out


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
        # 一人一频道仅一条申请记录（uq_joinreq_community_user 闭环）：
        # 无记录 → 新建；审核中 → 拒绝重复；被拒 → 复用原行原子重置为待审（可重新申请）
        req = db.execute(
            select(JoinRequest).where(
                JoinRequest.community_id == community.id,
                JoinRequest.user_id == user.id,
            )
        ).scalar_one_or_none()
        if req is not None and req.status == JOIN_PENDING:
            raise ConflictError("申请已在审核中")
        if req is None:
            req = JoinRequest(community_id=community.id, user_id=user.id)
            db.add(req)
        else:
            # 原子重置（仅 REJECTED 行可重置，防并发绕过）：审核留痕由 op_logs 承担
            db.execute(
                update(JoinRequest)
                .where(JoinRequest.id == req.id, JoinRequest.status == JOIN_REJECTED)
                .values(status=JOIN_PENDING, handler_id=None, handled_at=None, created_at=func.now())
            )
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
    # 原子递增（并发加入防丢计数；08-29 计数器审查统一整改）
    db.execute(
        update(Community)
        .where(Community.id == community.id)
        .values(member_count=Community.member_count + 1)
    )
    # 运营中心：记录加入事件（供新增成员数统计）
    log_event(db, community.id, user.id, "join")
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
    # 原子递减（不为负）
    db.execute(
        update(Community)
        .where(Community.id == community.id)
        .values(member_count=func.greatest(0, Community.member_count - 1))
    )
    # 运营中心：记录退出事件（供退出成员数统计）
    log_event(db, community.id, user.id, "leave")
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


def list_members(db: Session, community: Community, page: int, page_size: int, keyword: str | None = None) -> dict:
    """成员列表（按身份分组排序：owner/admin 优先）。

    keyword 可选：按用户名或昵称模糊匹配（用于管理后台成员搜索）。
    """
    base = select(Member).where(Member.community_id == community.id, Member.is_blocked.is_(False))
    if keyword:
        kws = f"%{keyword.strip()}%"
        uid_sub = select(User.id).where(or_(User.username.like(kws), User.nickname.like(kws)))
        base = base.where(Member.user_id.in_(uid_sub))
    total = len(db.execute(base.with_only_columns(Member.id)).scalars().all())
    stmt = (
        base
        .order_by(Member.member_type, Member.join_time)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    members = db.execute(stmt).scalars().all()
    return {"items": _decorate_members(db, members), "total": total, "page": page, "page_size": page_size}


def list_blacklist(db: Session, community: Community, page: int, page_size: int, keyword: str | None = None) -> dict:
    """黑名单列表（is_blocked=True 的成员）。"""
    base = select(Member).where(Member.community_id == community.id, Member.is_blocked.is_(True))
    if keyword:
        kws = f"%{keyword.strip()}%"
        uid_sub = select(User.id).where(or_(User.username.like(kws), User.nickname.like(kws)))
        base = base.where(Member.user_id.in_(uid_sub))
    total = len(db.execute(base.with_only_columns(Member.id)).scalars().all())
    stmt = (
        base
        .order_by(Member.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    members = db.execute(stmt).scalars().all()
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
            jo.user_avatar = u.avatar_url or ""
        out.append(jo)
    return out


def _ensure_admin(db: Session, community: Community, user: User) -> None:
    member = db.execute(
        select(Member).where(Member.community_id == community.id, Member.user_id == user.id)
    ).scalar_one_or_none()
    if member is None or member.member_type not in (MEMBER_OWNER, MEMBER_ADMIN):
        raise PermissionError_("需要频道主或管理员权限")
