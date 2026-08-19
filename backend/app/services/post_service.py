"""帖子业务逻辑：发帖/编辑/删除/置顶/精华/详情/帖子流/关注流（阶段 3）。

排序约定：
- latest：is_top desc（置顶恒顶）, id desc；游标 = 上一页最后一条的 id
- hot：is_top desc, like_count desc, id desc；游标 = "like_count:last_id"
- 置顶帖子数量少，分页时整段返回（不参与游标推进）
"""
from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.permissions import PERM_DELETE_POST, PERM_ESSENCE, PERM_TOP, require_perms
from app.core.response import NotFoundError, ParamError, PermissionError_
from app.models.board import Board
from app.models.community import Community
from app.models.follow import Follow
from app.models.like import Like
from app.models.member import MEMBER_ADMIN, MEMBER_OWNER, Member
from app.models.post import Post, POST_STATUS_DELETED, POST_STATUS_NORMAL
from app.models.user import User
from app.schemas.post import CreatePostRequest, PostOut, UpdatePostRequest
from app.services.op_log_service import log_op


def create_post(
    db: Session,
    community: Community,
    board: Board,
    user: User,
    payload: CreatePostRequest,
) -> PostOut:
    """发帖：需为频道成员且未被禁言/封禁；版块 allow_post_role_ids 非空时校验身份组。"""
    member = _require_member(db, community.id, user.id)
    _check_board_post_perm(db, community, board, user, member)
    rich, plain = _normalize_content(payload)
    _validate_at_users(db, community.id, rich)
    post = Post(
        community_id=community.id,
        board_id=board.id,
        author_id=user.id,
        title=payload.title,
        rich_content=rich,
        source_markdown=plain,
        images=payload.images,
    )
    db.add(post)
    # 原子自增，避免并发 read-modify-write 丢计数
    db.execute(update(Community).where(Community.id == community.id).values(post_count=Community.post_count + 1))
    db.commit()
    db.refresh(post)
    return post_out(db, post, current_user_id=user.id)


def update_post(
    db: Session, community: Community, post: Post, user: User, payload: UpdatePostRequest
) -> PostOut:
    """编辑帖子（仅作者本人，且频道未封禁）。"""
    if post.author_id != user.id:
        raise PermissionError_("只能编辑自己的帖子")
    _require_member(db, community.id, user.id)
    data = payload.model_dump(exclude_unset=True)
    if "content" in data or "rich_content" in data:
        rich, plain = _normalize_content(payload)
        _validate_at_users(db, community.id, rich)
        post.rich_content = rich
        post.source_markdown = plain
    if "title" in data:
        post.title = data["title"]
    if "images" in data:
        post.images = data["images"]
    db.commit()
    db.refresh(post)
    return post_out(db, post, current_user_id=user.id)


def delete_post(db: Session, community: Community, post: Post, user: User) -> None:
    """删除帖子（软删）：作者本人，或拥有 delete_post 权限的管理者；管理删除留痕。"""
    is_author = post.author_id == user.id
    if not is_author:
        require_perms(db, community.id, user, PERM_DELETE_POST)
    else:
        _require_member(db, community.id, user.id)
    post.status = POST_STATUS_DELETED
    # 原子递减（不为负）
    db.execute(
        update(Community)
        .where(Community.id == community.id)
        .values(post_count=func.greatest(0, Community.post_count - 1))
    )
    if not is_author:
        log_op(db, community.id, user.id, "delete_post", "post", post.id, {"author_id": post.author_id})
    db.commit()


def set_top(db: Session, community: Community, post: Post, user: User, is_top: bool) -> PostOut:
    """置顶/取消置顶（top 权限）。"""
    require_perms(db, community.id, user, PERM_TOP)
    post.is_top = is_top
    log_op(db, community.id, user.id, "set_top", "post", post.id, {"is_top": is_top})
    db.commit()
    db.refresh(post)
    return post_out(db, post, current_user_id=user.id)


def set_essence(db: Session, community: Community, post: Post, user: User, is_essence: bool) -> PostOut:
    """精华/取消精华（essence 权限）。"""
    require_perms(db, community.id, user, PERM_ESSENCE)
    post.is_essence = is_essence
    log_op(db, community.id, user.id, "set_essence", "post", post.id, {"is_essence": is_essence})
    db.commit()
    db.refresh(post)
    return post_out(db, post, current_user_id=user.id)


def get_post(db: Session, post_id: int, current_user_id: int | None) -> PostOut:
    """帖子详情（含互动状态）。"""
    post = db.get(Post, post_id)
    if post is None or post.status != POST_STATUS_NORMAL:
        raise NotFoundError("帖子不存在")
    return post_out(db, post, current_user_id=current_user_id)


# ---------- 帖子流 ----------


def feed(
    db: Session,
    community: Community,
    sort: str,
    cursor: str | None,
    page_size: int,
    current_user_id: int | None,
    board_id: int | None = None,
) -> dict:
    """频道帖子流：置顶恒顶；latest 按时间倒序，hot 按点赞数倒序；可选按版块过滤。"""
    if sort not in ("latest", "hot"):
        raise ParamError("sort 仅支持 latest / hot")

    # 置顶帖子（整段返回，不参与游标推进）
    top_stmt = (
        select(Post)
        .where(Post.community_id == community.id, Post.status == POST_STATUS_NORMAL, Post.is_top.is_(True))
        .order_by(Post.id.desc())
    )
    # 普通帖子分页（keyset）
    normal_stmt = (
        select(Post)
        .where(Post.community_id == community.id, Post.status == POST_STATUS_NORMAL, Post.is_top.is_(False))
    )
    if board_id:
        top_stmt = top_stmt.where(Post.board_id == board_id)
        normal_stmt = normal_stmt.where(Post.board_id == board_id)
    top_posts = db.execute(top_stmt).scalars().all()

    if sort == "latest":
        last_id = int(cursor) if cursor and cursor.isdigit() else None
        if last_id:
            normal_stmt = normal_stmt.where(Post.id < last_id)
        normal_stmt = normal_stmt.order_by(Post.id.desc())
    else:  # hot
        last_lc = last_hid = None
        if cursor and ":" in cursor:
            try:
                last_lc, last_hid = (int(x) for x in cursor.split(":", 1))
            except ValueError:
                last_lc = last_hid = None
        if last_lc is not None and last_hid is not None:
            normal_stmt = normal_stmt.where(
                or_(Post.like_count < last_lc, (Post.like_count == last_lc) & (Post.id < last_hid))
            )
        normal_stmt = normal_stmt.order_by(Post.like_count.desc(), Post.id.desc())

    normal_posts = db.execute(normal_stmt.limit(page_size)).scalars().all()

    items = top_posts + normal_posts
    has_more = len(normal_posts) == page_size
    next_cursor = None
    if has_more and normal_posts:
        last = normal_posts[-1]
        next_cursor = f"{last.like_count}:{last.id}" if sort == "hot" else str(last.id)
    return {
        "items": post_outs(db, items, current_user_id),
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


def global_feed(
    db: Session,
    sort: str,
    cursor: str | None,
    page_size: int,
    current_user_id: int | None,
) -> dict:
    """全站帖子流（首页用）：latest 时间倒序 / hot 点赞倒序，keyset 游标。"""
    if sort not in ("latest", "hot"):
        raise ParamError("sort 仅支持 latest / hot")
    stmt = select(Post).where(Post.status == POST_STATUS_NORMAL)
    if sort == "latest":
        last_id = int(cursor) if cursor and cursor.isdigit() else None
        if last_id:
            stmt = stmt.where(Post.id < last_id)
        stmt = stmt.order_by(Post.id.desc())
    else:  # hot
        last_lc = last_hid = None
        if cursor and ":" in cursor:
            try:
                last_lc, last_hid = (int(x) for x in cursor.split(":", 1))
            except ValueError:
                last_lc = last_hid = None
        if last_lc is not None and last_hid is not None:
            stmt = stmt.where(
                or_(Post.like_count < last_lc, (Post.like_count == last_lc) & (Post.id < last_hid))
            )
        stmt = stmt.order_by(Post.like_count.desc(), Post.id.desc())
    posts = db.execute(stmt.limit(page_size)).scalars().all()
    has_more = len(posts) == page_size
    next_cursor = None
    if has_more and posts:
        last = posts[-1]
        next_cursor = f"{last.like_count}:{last.id}" if sort == "hot" else str(last.id)
    return {
        "items": post_outs(db, posts, current_user_id),
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


def my_feed(
    db: Session,
    user: User,
    cursor: str | None,
    page_size: int,
) -> dict:
    """我关注的频道的帖子流（latest）。"""
    last_id = int(cursor) if cursor and cursor.isdigit() else None
    followed = db.execute(
        select(Follow.community_id).where(Follow.user_id == user.id)
    ).scalars().all()
    if not followed:
        return {"items": [], "next_cursor": None, "has_more": False}
    stmt = (
        select(Post)
        .where(
            Post.community_id.in_(followed),
            Post.status == POST_STATUS_NORMAL,
        )
    )
    if last_id:
        stmt = stmt.where(Post.id < last_id)
    stmt = stmt.order_by(Post.id.desc())
    posts = db.execute(stmt.limit(page_size)).scalars().all()
    has_more = len(posts) == page_size
    next_cursor = str(posts[-1].id) if has_more and posts else None
    return {
        "items": post_outs(db, posts, user.id),
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


# ---------- 组装 ----------


def post_outs(db: Session, posts: list[Post], current_user_id: int | None) -> list[PostOut]:
    """批量组装：作者/版块/频道/点赞/关注/成员 各一次 IN 查询（feed 用，避免 N+1）。"""
    if not posts:
        return []
    uids = {p.author_id for p in posts}
    bids = {p.board_id for p in posts}
    cids = {p.community_id for p in posts}
    pids = [p.id for p in posts]

    users = {u.id: u for u in db.execute(select(User).where(User.id.in_(uids))).scalars().all()}
    boards = {b.id: b for b in db.execute(select(Board).where(Board.id.in_(bids))).scalars().all()}
    comms = {c.id: c for c in db.execute(select(Community).where(Community.id.in_(cids))).scalars().all()}

    out_map: dict[int, PostOut] = {}
    for p in posts:
        o = PostOut.model_validate(p)
        u = users.get(p.author_id)
        if u:
            o.author_nickname = u.nickname or u.username
            o.author_avatar = u.avatar_url
        b = boards.get(p.board_id)
        if b:
            o.board_name = b.name
        c = comms.get(p.community_id)
        if c:
            o.community_name = c.name
        out_map[p.id] = o

    if current_user_id:
        liked_ids = set(
            db.execute(
                select(Like.post_id).where(
                    Like.post_id.in_(pids), Like.comment_id == 0, Like.user_id == current_user_id
                )
            ).scalars().all()
        )
        followed_cids = set(
            db.execute(
                select(Follow.community_id).where(
                    Follow.user_id == current_user_id, Follow.community_id.in_(cids)
                )
            ).scalars().all()
        )
        member_cids = set(
            db.execute(
                select(Member.community_id).where(
                    Member.user_id == current_user_id, Member.community_id.in_(cids)
                )
            ).scalars().all()
        )
        for p in posts:
            o = out_map[p.id]
            o.is_liked = p.id in liked_ids
            o.is_followed = p.community_id in followed_cids
            o.is_member = p.community_id in member_cids
    return [out_map[p.id] for p in posts]


# ---------- 组装 ----------


def post_out(db: Session, post: Post, current_user_id: int | None) -> PostOut:
    """帖子输出增强：作者昵称/头像、频道/版块名、互动状态。"""
    out = PostOut.model_validate(post)

    author = db.get(User, post.author_id)
    if author:
        out.author_nickname = author.nickname or author.username
        out.author_avatar = author.avatar_url
    board = db.get(Board, post.board_id)
    if board:
        out.board_name = board.name
    community = db.get(Community, post.community_id)
    if community:
        out.community_name = community.name

    if current_user_id:
        liked = db.execute(
            select(Like.id).where(
                Like.post_id == post.id, Like.comment_id == 0, Like.user_id == current_user_id
            )
        ).scalar_one_or_none()
        out.is_liked = liked is not None
        followed = db.execute(
            select(Follow.id).where(
                Follow.user_id == current_user_id, Follow.community_id == post.community_id
            )
        ).scalar_one_or_none()
        out.is_followed = followed is not None
        member = db.execute(
            select(Member.id).where(
                Member.community_id == post.community_id, Member.user_id == current_user_id
            )
        ).scalar_one_or_none()
        out.is_member = member is not None
    return out


# ---------- 内容规范化 ----------


def _normalize_content(payload) -> tuple[list, str]:
    """rich_content（4.4 分片）优先；否则 content 纯文本转单文本分片。返回 (分片, 纯文本)。

    纯文本提取规则：type1 text / type3 display_text / type2 at_user.nick / type8 topic_name / type4 emoji.char。
    """
    if payload.rich_content:
        rich = payload.rich_content
        parts = []
        for seg in rich:
            if not isinstance(seg, dict):
                continue
            t = seg.get("type")
            if t == 1 and seg.get("text"):
                parts.append(seg["text"])
            elif t == 2 and isinstance(seg.get("at_user"), dict):
                parts.append(f"@{seg['at_user'].get('nick', '')}")
            elif t == 3 and seg.get("display_text"):
                parts.append(seg["display_text"])
            elif t == 4 and isinstance(seg.get("emoji"), dict):
                parts.append(seg["emoji"].get("char", ""))
            elif t == 8 and isinstance(seg.get("topic"), dict):
                parts.append(f"#{seg['topic'].get('topic_name', '')}")
        return rich, "".join(parts).strip()
    if payload.content:
        return [{"type": 1, "text": payload.content}], payload.content
    raise ParamError("content 与 rich_content 至少提供一个")


def _validate_at_users(db: Session, community_id: int, rich: list) -> None:
    """@ 提及（type 2）目标必须是频道成员。"""
    at_ids = {
        seg["at_user"]["id"]
        for seg in rich
        if isinstance(seg, dict) and seg.get("type") == 2 and isinstance(seg.get("at_user"), dict)
    }
    if not at_ids:
        return
    member_ids = set(
        db.execute(
            select(Member.user_id).where(Member.community_id == community_id, Member.user_id.in_(at_ids))
        ).scalars().all()
    )
    invalid = at_ids - member_ids
    if invalid:
        raise ParamError(f"只能提及频道成员（id={sorted(invalid)} 不是成员）")


# ---------- 权限 ----------


def _require_member(db: Session, community_id: int, user_id: int) -> Member:
    """频道成员校验：频道须正常（未关闭/封禁），且成员未被拉黑/禁言。"""
    community = db.get(Community, community_id)
    if community is None or community.status != 0:
        raise NotFoundError("频道不存在")
    member = db.execute(
        select(Member).where(Member.community_id == community_id, Member.user_id == user_id)
    ).scalar_one_or_none()
    if member is None or member.is_blocked:
        raise PermissionError_("只有频道成员可以执行此操作")
    from datetime import datetime

    if member.shutup_expire_at and member.shutup_expire_at > datetime.now():
        raise PermissionError_("你已被禁言，无法操作")
    return member


def _check_board_post_perm(
    db: Session, community: Community, board: Board, user: User, member: Member
) -> None:
    """版块发帖权限：allow_post_role_ids 非空时，成员身份组必须命中（owner/admin 直接放行）。"""
    if member.member_type in (MEMBER_OWNER, MEMBER_ADMIN):
        return
    allowed = board.allow_post_role_ids or []
    if not allowed:
        return
    if member.role_id is None or member.role_id not in allowed:
        raise PermissionError_("该版块不允许你的身份组发帖")
