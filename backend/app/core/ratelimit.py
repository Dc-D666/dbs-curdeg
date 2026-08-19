"""接口限流（阶段 7）：Redis 计数窗口（固定窗口），429 + 3001。

用法：user=Depends(rate_limit("login", limit=10, window=60))
身份：优先取登录用户 id，未登录取真实客户端 IP（X-Forwarded-For）。
测试环境 settings.RATE_LIMIT_ENABLED=False（conftest 全局关闭，避免共享 Redis 串扰）。
"""
import logging

import redis
from fastapi import Request

from app.core.config import settings
from app.core.response import BizError

logger = logging.getLogger(__name__)


def _identity(request: Request, user_id: int | None) -> str:
    if user_id:
        return f"u{user_id}"
    xff = request.headers.get("x-forwarded-for", "")
    ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")
    return f"ip:{ip}"


def rate_limit(prefix: str, limit: int = 10, window: int = 60):
    """依赖工厂：固定窗口计数限流（Redis INCR + EXPIRE）。"""
    def _dependency(request: Request, user_id: int | None = None) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return
        try:
            r = redis.Redis(
                host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB,
                decode_responses=True,
            )
            key = f"rl:{prefix}:{_identity(request, user_id)}"
            n = r.incr(key)
            if n == 1:
                r.expire(key, window)
            if n > limit:
                raise BizError(code=3001, message="请求过于频繁，请稍后再试", http_status=429)
        except redis.RedisError:
            logger.warning("限流 Redis 不可用，放行 prefix=%s", prefix)

    return _dependency
