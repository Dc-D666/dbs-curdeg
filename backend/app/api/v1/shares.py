"""分享短链接口（阶段 5，文档⑭）。

- POST /api/v1/shares：生成短链（需登录）
- GET /s/{code}：跳转（根路径例外，nginx 反代到本路由；未登录/外部用户可打开）
"""
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.ratelimit import get_client_ip, rate_limit
from app.core.response import NotFoundError, ok
from app.db import get_db
from app.models.short_link import TARGET_COMMUNITY, TARGET_POST, TARGET_USER
from app.models.user import User
from app.services import share_service

router = APIRouter(tags=["shares"])
public_router = APIRouter(tags=["shares"])  # 根路径例外：/s/{code} 不挂 /api/v1


class CreateShareRequest(BaseModel):
    target_type: int = Field(ge=1, le=3)  # 1频道 2帖子 3用户
    target_id: int = Field(gt=0)


@router.post("/shares")
def create_share(
    payload: CreateShareRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """生成分享短链，返回 { code, url }。"""
    data = share_service.create_share(db, user, payload.target_type, payload.target_id)
    return ok(data=data, message="短链已生成")


@public_router.get("/s/{code}")
def resolve_share(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    _=Depends(rate_limit("share_resolve", limit=60, window=60)),
):
    """短链跳转：302 到前端页面（帖子/频道/用户）。"""
    # 取真实客户端 IP（可信代理追加的 XFF 最右值，无法被客户端伪造）
    client_ip = get_client_ip(request)
    path = share_service.resolve_share(db, code, client_ip)
    return RedirectResponse(url=path, status_code=302)
