"""分享短链业务逻辑（阶段 5，文档⑭分享与短链管理）。

- code：8 位随机（排除易混淆字符 0O1lI），撞库重试
- 跳转：GET /s/{code} 根路径（nginx 反代），按 target_type 302 到前端页面
- 计数：Redis 防刷（同 IP 60s 内只计一次），增量满 10 批量落库；
  过期链接由启动后台任务每日清理（懒查询也会拦过期）。
"""
import asyncio
import logging
import secrets

import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.response import NotFoundError
from app.models.community import Community
from app.models.post import Post, POST_STATUS_NORMAL
from app.models.short_link import ShortLink, TARGET_COMMUNITY, TARGET_POST, TARGET_USER
from app.models.user import User

logger = logging.getLogger(__name__)

CODE_LENGTH = 8
# 排除 0/O/1/l/I 等易混淆字符
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

# Redis 计数键
VISITS_KEY = "share:visits:{code}"       # 未落库的访问增量
UV_KEY = "share:uv:{code}:{ip}"          # 同 IP 去重标记（60s）
UV_TTL_SECONDS = 60
FLUSH_EVERY = 10                          # 每满 10 次批量落库

CLEANUP_INTERVAL_SECONDS = 6 * 3600       # 过期短链清理周期（6h）

# 前端页面路径映射（SPA history 路由）
_TARGET_PATH = {
    TARGET_COMMUNITY: "/c/{id}",
    TARGET_POST: "/p/{id}",
    TARGET_USER: "/users/{id}",
}


def _redis() -> redis.Redis:
    return redis.Redis(
        host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB,
        decode_responses=True,
    )


def _gen_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def _check_target(db: Session, target_type: int, target_id: int) -> None:
    """目标必须存在且可用。"""
    if target_type == TARGET_POST:
        post = db.get(Post, target_id)
        if post is None or post.status != POST_STATUS_NORMAL:
            raise NotFoundError("帖子不存在")
    elif target_type == TARGET_COMMUNITY:
        community = db.get(Community, target_id)
        if community is None or community.status != 0:
            raise NotFoundError("频道不存在")
    elif target_type == TARGET_USER:
        user = db.get(User, target_id)
        if user is None or user.status != 0:
            raise NotFoundError("用户不存在")
    else:
        raise NotFoundError("不支持的分享类型")


def create_share(
    db: Session, creator: User, target_type: int, target_id: int, expires_at=None
) -> dict:
    """生成短链：随机 code 撞库重试（5 次，唯一约束兜底）。"""
    _check_target(db, target_type, target_id)
    for _ in range(5):
        code = _gen_code()
        exists = db.execute(select(ShortLink.id).where(ShortLink.code == code)).scalar_one_or_none()
        if not exists:
            link = ShortLink(
                code=code,
                target_type=target_type,
                target_id=target_id,
                creator_id=creator.id,
                expires_at=expires_at,
            )
            db.add(link)
            db.commit()
            return {"code": code, "url": f"/s/{code}"}
    raise RuntimeError("短链生成失败，请重试")  # 撞库 5 次（概率可忽略）


def resolve_share(db: Session, code: str, client_ip: str | None = None) -> str:
    """解析短链：返回前端跳转路径；不存在/过期 → 404；计数（Redis 防刷 + 批量落库）。"""
    link = db.execute(select(ShortLink).where(ShortLink.code == code)).scalar_one_or_none()
    if link is None:
        raise NotFoundError("短链不存在")
    from datetime import datetime

    if link.expires_at and link.expires_at < datetime.now():
        raise NotFoundError("短链已过期")
    _count_visit(db, link, client_ip)
    path = _TARGET_PATH.get(link.target_type)
    if path is None:
        raise NotFoundError("不支持的分享类型")
    return path.format(id=link.target_id)


def _count_visit(db: Session, link: ShortLink, client_ip: str | None) -> None:
    """同 IP 60s 去重；增量满 FLUSH_EVERY 批量写回 DB 并重置。"""
    try:
        r = _redis()
        if client_ip and not r.set(UV_KEY.format(code=link.code, ip=client_ip), 1, ex=UV_TTL_SECONDS, nx=True):
            return  # 同一 IP 短时间重复访问，不计
        delta = r.incr(VISITS_KEY.format(code=link.code))
        if delta % FLUSH_EVERY == 0:
            link.visit_count += delta
            db.commit()
            r.delete(VISITS_KEY.format(code=link.code))
    except redis.RedisError:
        logger.warning("短链计数 Redis 不可用，跳过计数 code=%s", link.code)


def cleanup_expired(db: Session) -> int:
    """删除过期短链（每日后台任务调用）。"""
    from datetime import datetime

    expired = db.execute(
        select(ShortLink.id).where(ShortLink.expires_at.is_not(None), ShortLink.expires_at < datetime.now())
    ).scalars().all()
    if not expired:
        return 0
    from sqlalchemy import delete

    db.execute(delete(ShortLink).where(ShortLink.id.in_(expired)))
    db.commit()
    return len(expired)


async def cleanup_loop() -> None:
    """后台清理任务：每 CLEANUP_INTERVAL_SECONDS 跑一次（startup 时启动）。

    Redis/DB 操作经 asyncio.to_thread，避免同步阻塞事件循环。
    """
    from app.db import SessionLocal

    while True:
        try:
            db = SessionLocal()
            try:
                n = await asyncio.to_thread(cleanup_expired, db)
                if n:
                    logger.info("清理过期短链 %s 条", n)
            finally:
                try:
                    db.close()
                except Exception:
                    pass  # shutdown 取消时连接可能处于中间态
        except Exception:
            logger.exception("短链清理任务异常")
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
