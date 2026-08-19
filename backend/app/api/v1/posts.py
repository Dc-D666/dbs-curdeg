"""帖子接口：发帖/详情/编辑/删除/置顶/精华/帖子流/关注流（阶段 3）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_current_user_optional
from app.core.response import NotFoundError, ok
from app.db import get_db
from app.models.board import Board
from app.models.community import Community
from app.models.post import Post, POST_STATUS_NORMAL
from app.models.user import User
from app.schemas.post import CreatePostRequest, UpdatePostRequest
from app.services import post_service

router = APIRouter(tags=["posts"])


@router.post("/communities/{community_id}/boards/{board_id}/posts")
def create_post(
    community_id: int,
    board_id: int,
    payload: CreatePostRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发帖（需频道成员，校验版块发帖权限）。"""
    community, board = _get_community_board(db, community_id, board_id)
    return ok(data=post_service.create_post(db, community, board, user, payload), message="发帖成功")


@router.get("/communities/{community_id}/feed")
def feed(
    community_id: int,
    sort: str = Query("latest", pattern="^(latest|hot)$"),
    cursor: str | None = Query(None, description="游标：latest 为最后帖子 id，hot 为 like_count:id"),
    page_size: int = Query(20, ge=1, le=50),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """频道帖子流（置顶恒顶；latest 最新 / hot 热门；游客可见）。"""
    community = _get_community(db, community_id)
    uid = user.id if user else None
    return ok(data=post_service.feed(db, community, sort, cursor, page_size, uid))


@router.get("/me/feed")
def my_feed(
    cursor: str | None = Query(None),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我关注的频道的帖子流（latest）。"""
    return ok(data=post_service.my_feed(db, user, cursor, page_size))


@router.get("/posts/{post_id}")
def get_post(
    post_id: int,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """帖子详情（含作者/频道/版块信息 + 互动状态）。"""
    return ok(data=post_service.get_post(db, post_id, user.id if user else None))


@router.put("/posts/{post_id}")
def update_post(
    post_id: int,
    payload: UpdatePostRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """编辑帖子（仅作者本人）。"""
    post, community = _get_post_community(db, post_id)
    return ok(data=post_service.update_post(db, community, post, user, payload), message="已保存")


@router.delete("/posts/{post_id}")
def delete_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除帖子（软删；作者本人或频道主/管理员）。"""
    post, community = _get_post_community(db, post_id)
    post_service.delete_post(db, community, post, user)
    return ok(message="帖子已删除")


@router.post("/posts/{post_id}/top")
def set_top(
    post_id: int,
    is_top: bool = Query(True),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """置顶/取消置顶（仅频道主/管理员）。"""
    post, community = _get_post_community(db, post_id)
    return ok(data=post_service.set_top(db, community, post, user, is_top), message="已置顶" if is_top else "已取消置顶")


@router.post("/posts/{post_id}/essence")
def set_essence(
    post_id: int,
    is_essence: bool = Query(True),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """精华/取消精华（仅频道主/管理员）。"""
    post, community = _get_post_community(db, post_id)
    return ok(data=post_service.set_essence(db, community, post, user, is_essence), message="已设为精华" if is_essence else "已取消精华")


# ---------- 辅助 ----------


def _get_community(db: Session, community_id: int) -> Community:
    community = db.get(Community, community_id)
    if community is None or community.status != 0:
        raise NotFoundError("频道不存在")
    return community


def _get_community_board(db: Session, community_id: int, board_id: int) -> tuple[Community, Board]:
    community = _get_community(db, community_id)
    board = db.get(Board, board_id)
    if board is None or board.community_id != community_id or board.status != 0:
        raise NotFoundError("版块不存在")
    return community, board


def _get_post_community(db: Session, post_id: int) -> tuple[Post, Community]:
    post = db.get(Post, post_id)
    if post is None or post.status != POST_STATUS_NORMAL:
        raise NotFoundError("帖子不存在")
    community = db.get(Community, post.community_id)
    if community is None:
        raise NotFoundError("频道不存在")
    return post, community
