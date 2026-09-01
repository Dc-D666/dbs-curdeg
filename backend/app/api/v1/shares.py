"""分享短链接口（阶段 5 + P0，文档⑭）。

- POST /api/v1/shares：生成短链（需登录）
- GET /api/v1/shares：短链记录查询（需登录，可查自己的；管理员可全量）
- DELETE /api/v1/shares/{code}：短链失效（需登录，本人或管理员）
- GET /s/{code}：跳转（根路径例外，nginx 反代到本路由；未登录/外部用户可打开）
"""
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.ratelimit import get_client_ip, rate_limit
from app.core.response import NotFoundError, PermissionError_, ok
from app.db import get_db
from app.models.short_link import ShortLink, TARGET_COMMUNITY, TARGET_POST, TARGET_USER
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


@router.get("/communities/{community_id}/qr")
def community_qr(
    community_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """频道分享二维码 PNG：为频道生成分享短链并渲染为二维码图片。

    需要登录（频道成员/管理员），防止匿名滥用；短链本身公开可访问。
    """
    from app.models.community import Community
    from datetime import datetime

    community = db.get(Community, community_id)
    if community is None:
        raise NotFoundError("频道不存在")
    # 复用同频道已有未过期短链（避免每次请求都新建，短链表无累积）
    row = db.execute(
        select(ShortLink)
        .where(
            ShortLink.target_type == TARGET_COMMUNITY,
            ShortLink.target_id == community_id,
            (ShortLink.expires_at.is_(None)) | (ShortLink.expires_at > datetime.now()),
        )
        .order_by(ShortLink.id.desc())
    ).scalars().first()
    if row is not None:
        code = row.code
    else:
        data = share_service.create_share(db, user, TARGET_COMMUNITY, community_id)
        code = data["code"]
    # 用请求 Host 构造绝对短链地址（nginx 反代后 Host 为站点域名）
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "guild.weaxi.cn"
    scheme = request.headers.get("x-forwarded-proto", "https")
    url = f"{scheme}://{host}/s/{code}"
    try:
        import io

        import qrcode

        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png",
                        headers={"Cache-Control": "no-store"})
    except Exception:
        from app.core.response import BizError

        raise BizError(message="二维码生成失败")


@router.get("/shares")
def list_shares(
    target_type: int | None = Query(None, ge=1, le=3),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """短链记录查询：普通用户只能查自己生成的；系统管理员可全量。"""
    creator_id = None if user.user_type == 1 else user.id
    return ok(data=share_service.list_shares(db, creator_id, target_type, page, page_size))


@router.delete("/shares/{code}")
def invalidate_share(
    code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """短链失效：本人生成或系统管理员可操作。"""
    if user.user_type != 1:
        row = db.execute(
            select(ShortLink).where(ShortLink.code == code)
        ).scalar_one_or_none()
        if row is None or row.creator_id != user.id:
            raise PermissionError_("只能操作自己生成的短链")
    share_service.invalidate_share(db, code)
    return ok(message="短链已失效")


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
