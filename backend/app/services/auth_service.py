"""认证/用户业务逻辑：注册、登录、刷新、登出、改密、资料。"""
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.response import AuthError, ConflictError, ParamError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.user import (
    LoginRequest,
    RegisterRequest,
    TokenOut,
    UpdateProfileRequest,
    UserOut,
)
from app.services import email_service

# Redis 里 refresh token 黑名单前缀（登出后失效）
REFRESH_BLACKLIST_PREFIX = "refresh_blacklist:"


def _token_out(user: User) -> TokenOut:
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    return TokenOut(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def send_code(email: str) -> None:
    """发送注册验证码（同一邮箱可重复发，覆盖旧码）。"""
    email_service.send_email_code(email)


def register(db: Session, payload: RegisterRequest) -> TokenOut:
    # 校验验证码（先校验再查重，避免验证码被消耗后报错）
    if not email_service.verify_email_code(payload.email, payload.code):
        raise ParamError("验证码错误或已过期，请确认与邮件一致（邮件可能延迟，可点重发）")
    # 查重
    exists = db.execute(
        select(User).where(or_(User.username == payload.username, User.email == payload.email))
    ).scalar_one_or_none()
    if exists:
        raise ConflictError("用户名或邮箱已被注册")
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname or payload.username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_out(user)


def login(db: Session, payload: LoginRequest, client_ip: str = "") -> TokenOut:
    user = db.execute(
        select(User).where(or_(User.username == payload.account, User.email == payload.account))
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AuthError("用户名或密码错误")
    if user.status != 0:
        raise AuthError("账号不存在或已被封禁")
    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if client_ip:
        user.last_login_ip = client_ip[:45]
    db.commit()
    return _token_out(user)


def refresh(db: Session, refresh_token: str) -> TokenOut:
    user_id = decode_token(refresh_token, expected_type="refresh")
    if user_id is None:
        raise AuthError("刷新令牌无效或已过期")
    import redis as redis_lib

    r = redis_lib.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    if r.get(f"{REFRESH_BLACKLIST_PREFIX}{refresh_token}"):
        raise AuthError("刷新令牌已被注销")
    user = db.get(User, user_id)
    if user is None or user.status != 0:
        raise AuthError("账号不存在或已被封禁")
    return _token_out(user)


def logout(refresh_token: str) -> None:
    """把 refresh token 加入黑名单直至其自然过期。"""
    import redis as redis_lib

    r = redis_lib.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    r.setex(
        f"{REFRESH_BLACKLIST_PREFIX}{refresh_token}",
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        "1",
    )


def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise ParamError("原密码错误")
    user.password_hash = hash_password(new_password)
    db.commit()


def send_reset_code(db: Session, email: str) -> None:
    """忘记密码：发送重置验证码（邮箱需已注册，防探测不返回 200 差异）。"""
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        # 与"已发送"一致返回，避免枚举已注册邮箱
        return
    email_service.send_reset_code(email)


def reset_password(db: Session, email: str, code: str, new_password: str) -> None:
    """重置密码：校验重置验证码 → 更新密码。"""
    if not email_service.verify_reset_code(email, code):
        raise ParamError("验证码错误或已过期")
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or user.status != 0:
        raise ParamError("账号不存在或不可用")
    user.password_hash = hash_password(new_password)
    db.commit()


def deactivate(db: Session, user: User) -> None:
    """用户注销（软注销）：status=2，清空登录凭据相关的通知继续保留。"""
    user.status = 2
    db.commit()


def update_profile(db: Session, user: User, payload: UpdateProfileRequest) -> UserOut:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


def get_user_out(user: User) -> UserOut:
    return UserOut.model_validate(user)
