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
# 重置密码验证码（独立通道，与注册码不冲突）
RESET_PREFIX = "reset_code:"
RESET_TTL = 300
# 每邮箱每日上限（防轰炸）
DAILY_LIMIT = 10
DAILY_KEY_PREFIX = "email_daily:"
DAILY_RESET_PREFIX = "reset_daily:"


def _redis() -> redis.Redis:
    return redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)


def _get_or_create_code(r: redis.Redis, email: str) -> str:
    """取现有验证码或生成新码（复用逻辑，可独立测试）。"""
    key = f"{CODE_PREFIX}{email}"
    code = r.get(key)
    if code is None:
        code = f"{secrets.randbelow(1000000):06d}"
        r.setex(key, CODE_TTL, code)
    return code


def send_email_code(email: str) -> str:
    """发送验证码。

    关键：若该邮箱已有未过期验证码则**复用旧码并重发邮件**（不生成新码），
    避免邮件延迟期间重复点击导致旧码失效（用户填的码与 Redis 不一致 → 400）。
    """
    r = _redis()
    daily_key = f"{DAILY_KEY_PREFIX}{email}:{date.today().isoformat()}"
    used = int(r.get(daily_key) or 0)
    if used >= DAILY_LIMIT:
        raise RuntimeError("该邮箱今日发送次数已达上限")
    code = _get_or_create_code(r, email)
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


def send_reset_code(email: str) -> str:
    """发送重置密码验证码（独立通道；含每日上限）。"""
    r = _redis()
    daily_key = f"{DAILY_RESET_PREFIX}{email}:{date.today().isoformat()}"
    used = int(r.get(daily_key) or 0)
    if used >= DAILY_LIMIT:
        raise RuntimeError("该邮箱今日重置次数已达上限")
    key = f"{RESET_PREFIX}{email}"
    code = r.get(key)
    if code is None:
        code = f"{secrets.randbelow(1000000):06d}"
        r.setex(key, RESET_TTL, code)
    r.incr(daily_key)
    r.expire(daily_key, 86400)
    _send_reset(email, code)
    logger.info("重置验证码已发送至 %s", email)
    return code


def verify_reset_code(email: str, code: str) -> bool:
    """校验重置验证码（一次性）。"""
    r = _redis()
    key = f"{RESET_PREFIX}{email}"
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


def _send_reset(to_addr: str, code: str) -> None:
    """发送重置密码验证码邮件（P0：忘记密码/邮箱找回）。"""
    body = (
        f"【SDUdiscord】您的密码重置验证码是 {code}，5 分钟内有效。"
        "如非本人操作请忽略本邮件。"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header("SDUdiscord 密码重置验证码", "utf-8")
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to_addr

    try:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM or settings.SMTP_USER, [to_addr], msg.as_string())
    except Exception as e:
        logger.error("重置邮件发送失败 %s -> %s: %s", to_addr, e, e)
        raise
