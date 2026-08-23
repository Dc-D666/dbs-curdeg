"""帖子接口：发帖/详情/编辑/删除/置顶/精华/帖子流/关注流（阶段 3）+ Feed 热度策略（阶段 5）。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_current_user_optional, require_perms
from app.core.response import NotFoundError, ok
from app.db import get_db
from app.models.board import Board
from app.models.community import Community
from app.models.post import Post, POST_STATUS_NORMAL
from app.models.user import User
from app.schemas.post import CreatePostRequest, UpdatePostRequest
from app.services import heat_service, post_service
from app.ws import events

router = APIRouter(tags=["posts"])


class FeedStrategyUpdate(BaseModel):
    """频道 Feed 热度策略更新（部分更新，全部可选）。"""
    sort_rule: int | None = Field(default=None, ge=0, le=2, description="0最新 1热度 2精华优先")
    weight_like: int | None = Field(default=None, ge=0, le=100)
    weight_comment: int | None = Field(default=None, ge=0, le=100)
    weight_favorite: int | None = Field(default=None, ge=0, le=100)
    decay_hours: int | None = Field(default=None, ge=1, le=720, description="时间衰减系数（小时）")
    top_weight: int | None = Field(default=None, ge=0, le=10000, description="置顶帖权重")
    cache_ttl: int | None = Field(default=None, ge=30, le=86400, description="热度缓存秒数")


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
    post = post_service.create_post(db, community, board, user, payload)
    # P1 ③：向频道在线成员广播新内容（仅成员、排除作者），触发前端「有 N 条新讨论」药丸
    events.push_feed_new(db, community.id, "post", post.id, exclude_user_id=user.id)
    return ok(data=post, message="发帖成功")


@router.get("/communities/{community_id}/feed")
def feed(
    community_id: int,
    sort: str = Query("latest", pattern="^(latest|hot)$"),
    board_id: int | None = Query(None, description="按版块过滤"),
    cursor: str | None = Query(None, description="游标：latest 为最后帖子 id，hot 为页码"),
    page_size: int = Query(20, ge=1, le=50),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """频道帖子流（latest 最新 / hot 热度分倒序，阶段 5；可选按版块过滤；游客可见）。"""
    community = _get_community(db, community_id)
    uid = user.id if user else None
    return ok(data=post_service.feed(db, community, sort, cursor, page_size, uid, board_id))


@router.get("/feed")
def global_feed(
    sort: str = Query("latest", pattern="^(latest|hot)$"),
    cursor: str | None = Query(None, description="游标：latest 为最后帖子 id，hot 为 like_count:id"),
    page_size: int = Query(20, ge=1, le=50),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """全站帖子流（首页）：latest 最新 / hot 热门；游客可见。"""
    uid = user.id if user else None
    return ok(data=post_service.global_feed(db, sort, cursor, page_size, uid))


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


# ---------- Feed 热度策略（阶段 5） ----------


@router.get("/communities/{community_id}/feed-strategy")
def get_feed_strategy(
    community_id: int,
    db: Session = Depends(get_db),
):
    """频道 Feed 热度策略（未配置时返回默认值；游客可读）。"""
    community = _get_community(db, community_id)
    s = heat_service.get_strategy(db, community.id)
    return ok(data={
        "sort_rule": s.sort_rule,
        "weight_like": s.weight_like,
        "weight_comment": s.weight_comment,
        "weight_favorite": s.weight_favorite,
        "decay_hours": s.decay_hours,
        "top_weight": s.top_weight,
        "cache_ttl": s.cache_ttl,
    })


@router.put("/communities/{community_id}/feed-strategy")
def update_feed_strategy(
    community_id: int,
    payload: FeedStrategyUpdate,
    member=Depends(require_perms("member_manage")),
    db: Session = Depends(get_db),
):
    """更新频道 Feed 热度策略（需 member_manage 权限）；改动即时生效并清热度缓存。"""
    community = _get_community(db, community_id)
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    s = heat_service.update_strategy(db, community.id, patch)
    return ok(data={
        "sort_rule": s.sort_rule,
        "weight_like": s.weight_like,
        "weight_comment": s.weight_comment,
        "weight_favorite": s.weight_favorite,
        "decay_hours": s.decay_hours,
        "top_weight": s.top_weight,
        "cache_ttl": s.cache_ttl,
    }, message="热度策略已更新")


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
    if community is None or community.status != 0:
        raise NotFoundError("频道不存在")
    return post, community
