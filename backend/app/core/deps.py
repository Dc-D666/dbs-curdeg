"""FastAPI 依赖注入：数据库会话、当前用户。"""
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.response import AuthError
from app.core.security import decode_token
from app.db import get_db
from app.models.user import User


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """从 Authorization: Bearer <token> 解析当前用户。"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AuthError("未登录")
    token = auth[len("Bearer "):].strip()
    user_id = decode_token(token, expected_type="access")
    if user_id is None:
        raise AuthError()
    user = db.get(User, user_id)
    if user is None or user.status != 0:
        raise AuthError("账号不存在或已被封禁")
    return user


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """可选登录：未带 token 时返回 None（用于公开接口的个性化数据）。"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):].strip()
    user_id = decode_token(token, expected_type="access")
    if user_id is None:
        return None
    return db.get(User, user_id)
