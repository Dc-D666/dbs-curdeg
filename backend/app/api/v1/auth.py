"""认证接口：验证码、注册、登录、刷新、登出、改密。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.ratelimit import rate_limit
from app.core.response import ok
from app.db import get_db
from app.models.user import User
from app.schemas.user import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendCodeRequest,
    TokenOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-code", dependencies=[Depends(rate_limit("send_code", limit=10, window=60))])
def send_code(payload: SendCodeRequest):
    """发送注册邮箱验证码（同 IP 1 分钟最多 10 次）。"""
    auth_service.send_code(payload.email)
    return ok(message="验证码已发送")


@router.post("/register", dependencies=[Depends(rate_limit("register", limit=10, window=60))])
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """注册：邮箱验证码 + 用户名 + 密码（同 IP 1 分钟最多 10 次）。"""
    return ok(data=auth_service.register(db, payload), message="注册成功")


@router.post("/login", dependencies=[Depends(rate_limit("login", limit=20, window=60))])
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """登录：用户名或邮箱 + 密码（同 IP 1 分钟最多 20 次，防爆破）。"""
    from app.core.ratelimit import get_client_ip

    return ok(
        data=auth_service.login(db, payload, client_ip=get_client_ip(request)),
        message="登录成功",
    )


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """刷新 access token。"""
    return ok(data=auth_service.refresh(db, payload.refresh_token))


@router.post("/logout")
def logout(payload: RefreshRequest):
    """登出：注销 refresh token。"""
    auth_service.logout(payload.refresh_token)
    return ok(message="已登出")


@router.put("/password")
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改密码。"""
    auth_service.change_password(db, user, payload.old_password, payload.new_password)
    return ok(message="密码已修改")


@router.post("/forgot-password", dependencies=[Depends(rate_limit("send_code", limit=10, window=60))])
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """忘记密码：发送重置验证码（未注册邮箱也返回成功，防枚举）。"""
    auth_service.send_reset_code(db, payload.email)
    return ok(message="验证码已发送（若邮箱已注册）")


@router.post("/reset-password", dependencies=[Depends(rate_limit("reset_password", limit=10, window=60))])
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """重置密码：验证码 + 新密码。"""
    auth_service.reset_password(db, payload.email, payload.code, payload.new_password)
    return ok(message="密码已重置，请重新登录")
