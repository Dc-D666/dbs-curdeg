"""帖子业务逻辑：发帖/编辑/删除/置顶/精华/详情/帖子流/关注流（阶段 3）。

排序约定：
- latest：is_top desc（置顶恒顶）, id desc；游标 = 上一页最后一条的 id
- hot：is_top desc, like_count desc, id desc；游标 = "like_count:last_id"
- 置顶帖子数量少，分页时整段返回（不参与游标推进）
"""
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.response import NotFoundError, ParamError, PermissionError_
from app.models.board import Board
from app.models.community import Community
from app.models.follow import Follow
from app.models.like import Like
from app.models.member import MEMBER_ADMIN, MEMBER_OWNER, Member
from app.models.post import Post, POST_STATUS_DELETED, POST_STATUS_NORMAL
from app.models.user import User
from app.schemas.post import CreatePostRequest, PostOut, UpdatePostRequest


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

    post = Post(
        community_id=community.id,
        board_id=board.id,
        author_id=user.id,
        title=payload.title,
        rich_content=[{"type": 1, "text": payload.content}],
        source_markdown=payload.content,
        images=payload.images,
    )
    db.add(post)
    community.post_count += 1
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
    if "content" in data and data["content"] is not None:
        post.rich_content = [{"type": 1, "text": data["content"]}]
        post.source_markdown = data["content"]
    if "title" in data:
        post.title = data["title"]
    if "images" in data:
        post.images = data["images"]
    db.commit()
    db.refresh(post)
    return post_out(db, post, current_user_id=user.id)


def delete_post(db: Session, community: Community, post: Post, user: User) -> None:
    """删除帖子（软删）：作者本人或频道主/管理员。"""
    member = _require_member(db, community.id, user.id)
    if post.author_id != user.id and member.member_type not in (MEMBER_OWNER, MEMBER_ADMIN):
        raise PermissionError_("只能删除自己的帖子，或需要频道主/管理员权限")
    post.status = POST_STATUS_DELETED
    community.post_count = max(0, community.post_count - 1)
    db.commit()


def set_top(db: Session, community: Community, post: Post, user: User, is_top: bool) -> PostOut:
    """置顶/取消置顶（仅频道主/管理员）。"""
    _ensure_moderator(db, community.id, user.id)
    post.is_top = is_top
    db.commit()
    db.refresh(post)
    return post_out(db, post, current_user_id=user.id)


def set_essence(db: Session, community: Community, post: Post, user: User, is_essence: bool) -> PostOut:
    """精华/取消精华（仅频道主/管理员）。"""
    _ensure_moderator(db, community.id, user.id)
    post.is_essence = is_essence
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
) -> dict:
    """频道帖子流：置顶恒顶；latest 按时间倒序，hot 按点赞数倒序。"""
    if sort not in ("latest", "hot"):
        raise ParamError("sort 仅支持 latest / hot")

    # 置顶帖子（整段返回，不参与游标推进）
    top_stmt = (
        select(Post)
        .where(Post.community_id == community.id, Post.status == POST_STATUS_NORMAL, Post.is_top.is_(True))
        .order_by(Post.id.desc())
    )
    top_posts = db.execute(top_stmt).scalars().all()

    # 普通帖子分页（keyset）
    normal_stmt = (
        select(Post)
        .where(Post.community_id == community.id, Post.status == POST_STATUS_NORMAL, Post.is_top.is_(False))
    )
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
        "items": [post_out(db, p, current_user_id) for p in items],
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
        "items": [post_out(db, p, user.id) for p in posts],
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


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


# ---------- 权限 ----------


def _require_member(db: Session, community_id: int, user_id: int) -> Member:
    member = db.execute(
        select(Member).where(Member.community_id == community_id, Member.user_id == user_id)
    ).scalar_one_or_none()
    if member is None or member.is_blocked:
        raise PermissionError_("只有频道成员可以执行此操作")
    from datetime import datetime

    if member.shutup_expire_at and member.shutup_expire_at > datetime.now():
        raise PermissionError_("你已被禁言，无法操作")
    return member


def _ensure_moderator(db: Session, community_id: int, user_id: int) -> Member:
    member = _require_member(db, community_id, user_id)
    if member.member_type not in (MEMBER_OWNER, MEMBER_ADMIN):
        raise PermissionError_("需要频道主或管理员权限")
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
