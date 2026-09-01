"""Feed 热度服务（阶段 5，文档⑮Feed 流与排序管理）。

热度公式（可配置权重）：
    score = like*weight_like + comment*weight_comment + favorite*weight_favorite
            + top_weight(置顶) ，再乘以指数时间衰减 exp(-age_hours / decay_hours)

- 策略：feed_strategies 表每频道一行（GET/PUT /communities/{cid}/feed-strategy 管理，
  未配置时用默认值，GET 不落库、PUT upsert）
- 缓存：Redis ZSET feed:hot:{cid}（全站 feed:hot:all），member=post_id、score=热分；
  读取时惰性重建（TTL=cache_ttl），点赞/评论/发帖时增量更新单帖热分（zset 不存在则跳过）
- 分页：读取 zset 全量有序 id → SQL IN 取回 → 按 zset 顺序排列 → 页码式游标
  （与 latest 的 id 游标格式不同但互不可见，前端仅透传字符串）
- 收藏计数：posts.favorite_count 由 favorite_service 用 SQL 原子自增维护；
  favorites 上的 trg_favorites_ai/ad 只往 counter_audit 写台账，不动计数列，
  所以不会双加。逐帖与 favorites 实数零差异，直接取列值即可。
  （旧版这里写死 favorite_count = 0，注释称「favorites 表尚未实现」，
  但表与计数列都在、且有 3,011 行真实收藏，weight_favorite=3 因而已生效。）
"""
import math
import time
from datetime import datetime

import redis
from functools import lru_cache
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.feed_strategy import FeedStrategy, SORT_HOT, SORT_LATEST, SORT_ESSENCE
from app.models.post import Post, POST_STATUS_NORMAL

ZKEY = "feed:hot:{scope}"          # scope = community_id 或 "all"
ZSET_LIMIT = 500                   # 单次缓存最多纳入的帖子数（课设规模足够）
DEFAULT_TTL = 300

# 默认策略（与 FeedStrategy 模型列默认一致；模型 default 仅 INSERT 时生效，
# 瞬时对象属性为 None，因此这里显式兜底）
DEFAULTS: dict = {
    "sort_rule": SORT_HOT,
    "weight_like": 1,
    "weight_comment": 2,
    "weight_favorite": 3,
    "decay_hours": 24,
    "top_weight": 100,
    "cache_ttl": 300,
}

# 全站热度流使用默认权重（各频道自定义权重只影响本频道流）
ALL_SCOPE = "all"


_redis_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    """复用模块级连接（避免每次调用新建连接）。"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB,
            decode_responses=True,
        )
    return _redis_client


def _zkey(scope: int | str) -> str:
    return ZKEY.format(scope=scope)


# ---------- 策略 ----------


def get_strategy(db: Session, community_id: int | None) -> FeedStrategy:
    """频道热度策略（未配置时返回默认值对象，不落库）。"""
    s = None
    if community_id is not None:
        s = db.execute(
            select(FeedStrategy).where(FeedStrategy.community_id == community_id)
        ).scalar_one_or_none()
    if s is None:
        s = FeedStrategy(community_id=community_id or 0)
    _apply_defaults(s)
    return s


def _apply_defaults(s: FeedStrategy) -> None:
    """瞬时对象列默认不生效，显式兜底（模型 default 仅 INSERT 时生效）。"""
    for k, v in DEFAULTS.items():
        if getattr(s, k) is None:
            setattr(s, k, v)


def _default_strategy() -> FeedStrategy:
    """全站热度流使用的默认权重策略对象（字段已兜底，可安全计算）。"""
    s = FeedStrategy(community_id=0)
    _apply_defaults(s)
    return s


def update_strategy(db: Session, community_id: int, patch: dict) -> FeedStrategy:
    """更新频道热度策略（upsert），并清掉热度缓存。"""
    s = db.execute(
        select(FeedStrategy).where(FeedStrategy.community_id == community_id)
    ).scalar_one_or_none()
    if s is None:
        s = FeedStrategy(community_id=community_id)
        db.add(s)
    allowed = {
        "sort_rule": SORT_LATEST, "weight_like": 1, "weight_comment": 1,
        "weight_favorite": 1, "decay_hours": 1, "top_weight": 1, "cache_ttl": 1,
    }
    for k, v in patch.items():
        if k not in allowed:
            continue
        setattr(s, k, v)
    db.commit()
    try:
        _redis().delete(_zkey(community_id), _zkey(ALL_SCOPE))
    except redis.RedisError:
        pass
    return s


# ---------- 热度计算 ----------


def hot_score(post: Post, s: FeedStrategy, now: datetime | None = None) -> float:
    """单帖热度分（指数时间衰减）。"""
    now = now or datetime.now()
    age_hours = max(0.0, (now - post.created_at).total_seconds() / 3600)
    decay = math.exp(-age_hours / max(1, s.decay_hours))
    score = (
        post.like_count * max(0, s.weight_like)
        + post.comment_count * max(0, s.weight_comment)
        + post.favorite_count * max(0, s.weight_favorite)
    ) * decay
    if post.is_top:
        score += max(0, s.top_weight)
    return round(score, 4)


# ---------- 缓存 ----------


def rebuild_cache(db: Session, community_id: int | None = None) -> int:
    """重建频道（community_id）或全站（None）热度 zset，返回帖子数。"""
    s = get_strategy(db, community_id)
    stmt = select(Post).where(Post.status == POST_STATUS_NORMAL)
    if community_id is not None:
        stmt = stmt.where(Post.community_id == community_id)
    posts = db.execute(stmt).scalars().all()
    r = _redis()
    key = _zkey(community_id if community_id is not None else ALL_SCOPE)
    pipe = r.pipeline()
    pipe.delete(key)
    if posts:
        pipe.zadd(key, {str(p.id): hot_score(p, s) for p in posts})
    pipe.expire(key, s.cache_ttl or DEFAULT_TTL)
    pipe.execute()
    return len(posts)


def get_hot_ids(db: Session, community_id: int | None = None, limit: int = ZSET_LIMIT) -> list[int]:
    """按热分倒序的帖子 id 列表（缓存不存在时惰性重建）。"""
    r = _redis()
    key = _zkey(community_id if community_id is not None else ALL_SCOPE)
    try:
        if not r.exists(key):
            rebuild_cache(db, community_id)
    except redis.RedisError:
        rebuild_cache(db, community_id)
    try:
        members = r.zrevrange(key, 0, limit - 1)
    except redis.RedisError:
        return []
    return [int(m) for m in members]


def bump(db: Session, post: Post, community_id: int) -> None:
    """互动后增量更新单帖热分（缓存不存在时跳过，读取时惰性重建兜底）。"""
    try:
        r = _redis()
    except redis.RedisError:
        return
    key = _zkey(community_id)
    try:
        if not r.exists(key):
            return
        s = get_strategy(db, community_id)
        r.zadd(key, {str(post.id): hot_score(post, s)})
        # 全站缓存同步更新（用默认权重，字段已兜底可安全计算）
        all_key = _zkey(ALL_SCOPE)
        if r.exists(all_key):
            r.zadd(all_key, {str(post.id): hot_score(post, _default_strategy())})
    except redis.RedisError:
        pass


def remove(db: Session, post_id: int, community_id: int) -> None:
    """删除/下架帖子时从热度 zset 移除，避免占用缓存 slot 导致 offset 分页错位。"""
    try:
        r = _redis()
        r.zrem(_zkey(community_id), str(post_id))
        r.zrem(_zkey(ALL_SCOPE), str(post_id))
    except redis.RedisError:
        pass


# ---------- 热度分页 ----------


def hot_feed(db: Session, community_id: int | None, page: int, page_size: int, board_id: int | None = None) -> dict:
    """热度帖子分页：zset 顺序 → SQL 取回（可按版块过滤）→ offset 分页。返回 (posts, next_cursor, has_more)。"""
    page = max(1, int(page))
    ids = get_hot_ids(db, community_id)
    if not ids:
        return [], None, False
    stmt = select(Post).where(Post.id.in_(ids), Post.status == POST_STATUS_NORMAL)
    if board_id is not None:
        stmt = stmt.where(Post.board_id == board_id)  # 过滤下沉到分页前，避免 offset 错位
    posts = db.execute(stmt).scalars().all()
    order = {pid: i for i, pid in enumerate(ids)}
    posts.sort(key=lambda p: order.get(p.id, len(order)))
    start = (page - 1) * page_size
    items = posts[start:start + page_size]
    has_more = start + page_size < len(posts)
    next_cursor = str(page + 1) if has_more else None
    return items, next_cursor, has_more
