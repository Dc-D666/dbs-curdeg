"""邮箱服务：QQMail SMTP 发送验证码（阶段 1 注册用）。

配置（deploy/.env）：
  SMTP_HOST=smtp.qq.com  SMTP_PORT=465  SMTP_USER=<发件邮箱>
  SMTP_PASSWORD=<授权码>  SMTP_FROM=<发件邮箱>
"""
import logging
import secrets
import smtplib
from datetime import date
from email.header import Header
from email.mime.text import MIMEText

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# 验证码 Redis key 前缀与有效期（秒）
CODE_PREFIX = "email_code:"
CODE_TTL = 300  # 5 分钟
# 每邮箱每日上限（防轰炸）
DAILY_LIMIT = 10
DAILY_KEY_PREFIX = "email_daily:"


def _redis() -> redis.Redis:
    return redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)


def send_email_code(email: str) -> str:
    """生成验证码、落 Redis、发送邮件；返回验证码（便于测试/演示）。"""
    r = _redis()
    daily_key = f"{DAILY_KEY_PREFIX}{email}:{date.today().isoformat()}"
    used = int(r.get(daily_key) or 0)
    if used >= DAILY_LIMIT:
        raise RuntimeError("该邮箱今日发送次数已达上限")
    code = f"{secrets.randbelow(1000000):06d}"
    r.setex(f"{CODE_PREFIX}{email}", CODE_TTL, code)
    r.incr(daily_key)
    r.expire(daily_key, 86400)
    _send(email, code)
    logger.info("验证码已发送至 %s", email)
    return code


def verify_email_code(email: str, code: str) -> bool:
    """校验验证码（校验通过即删除，一次性）。"""
    r = _redis()
    key = f"{CODE_PREFIX}{email}"
    stored = r.get(key)
    if stored is None or stored != code:
        return False
    r.delete(key)
    return True


def _send(to_addr: str, code: str) -> None:
    """通过 QQMail SMTP 发送验证码邮件。"""
    body = (
        f"【SDUdiscord】您的注册验证码是 {code}，5 分钟内有效。"
        "如非本人操作请忽略本邮件。"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header("SDUdiscord 注册验证码", "utf-8")
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to_addr

    try:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM or settings.SMTP_USER, [to_addr], msg.as_string())
    except Exception as e:  # 发送失败不致命，但需暴露
        logger.error("邮件发送失败 %s -> %s: %s", to_addr, e, e)
        raise
