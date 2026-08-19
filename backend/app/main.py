"""仿腾讯频道 API 入口。

模块路由：
  /api/v1/auth   账号体系（注册/登录/JWT）
  /api/v1/users  用户资料
  /ws             WebSocket 实时通知（阶段 5）
  （后续阶段追加 ai/notification）
"""
import asyncio

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.v1 import auth, boards, comments, communities, interact, manage, members, notifications, posts, roles, search, shares, topics, uploads, users
from app.core.config import settings
from app.core.security import decode_token
from app.db import get_db
from app.models.user import User
from app.services import share_service
from app.ws import events
from app.ws.manager import manager

app = FastAPI(
    title="SDUdiscord API",
    version=settings.APP_VERSION,
    description="Web + Android 双端共用接口（仿腾讯频道课设）",
)

# CORS：生产收紧为前端域名（allow_origins 与 allow_credentials 不能通配+凭据并存）
_origins = settings.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False if "*" in _origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """统一业务响应：HTTP 状态码 + body code 并存。"""
    biz_code = getattr(exc, "biz_code", 1000)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": biz_code, "message": exc.detail, "data": None},
    )


# 字段级校验失败的友好提示（按 body 字段名映射；pydantic 默认英文消息不可直接展示）
_FIELD_HINTS = {
    "username": "用户名需为 3-32 位字母、数字或下划线",
    "email": "邮箱格式不正确",
    "code": "验证码为 6 位数字",
    "password": "密码至少 6 位，且需同时包含字母和数字",
    "account": "账号需为 3-64 位字符",
    "refresh_token": "refresh_token 不能为空",
    "old_password": "原密码不能为空",
    "new_password": "新密码至少 6 位，且需同时包含字母和数字",
}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """参数校验失败统一为 400 + 2001，message 给出首个可读的错误原因。"""
    errors = []
    message = "参数错误"
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", [])]
        field = loc[-1] if loc and loc[0] == "body" else None
        if field and field in _FIELD_HINTS and message == "参数错误":
            message = _FIELD_HINTS[field]
        errors.append(
            {
                "loc": loc,
                "msg": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
        )
    return JSONResponse(
        status_code=400,
        content={"code": 2001, "message": message, "data": {"errors": errors}},
    )


API_V1 = "/api/v1"
app.include_router(auth.router, prefix=API_V1)
app.include_router(users.router, prefix=API_V1)
app.include_router(communities.router, prefix=API_V1)
app.include_router(boards.router, prefix=API_V1)
app.include_router(members.router, prefix=API_V1)
app.include_router(uploads.router, prefix=API_V1)
app.include_router(posts.router, prefix=API_V1)
app.include_router(comments.router, prefix=API_V1)
app.include_router(interact.router, prefix=API_V1)
app.include_router(topics.router, prefix=API_V1)
app.include_router(roles.router, prefix=API_V1)
app.include_router(manage.router, prefix=API_V1)
app.include_router(search.router, prefix=API_V1)
app.include_router(notifications.router, prefix=API_V1)
app.include_router(shares.router, prefix=API_V1)
# 短链跳转：根路径例外（nginx 反代 /s/ 到本路由，方案 §5.1）
app.include_router(shares.public_router)


@app.on_event("startup")
async def _capture_ws_loop() -> None:
    """捕获 ASGI 主事件循环，供同步端点 run_coroutine_threadsafe 投递 WS 推送。"""
    events.set_ws_loop(asyncio.get_running_loop())
    # 过期短链每日清理（后台任务）
    asyncio.create_task(share_service.cleanup_loop())


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, db: Session = Depends(get_db)) -> None:
    """WebSocket 通知（协议见 详细开发方案.md §5.3）。

    首帧 {type: auth, token} 认证，10s 超时未认证断开（4401）；
    心跳：收到 {type: ping} 回 {type: pong}；断线自动清理连接。
    """
    user_id: int | None = None
    await ws.accept()
    # 首帧认证：10s 超时
    try:
        first = await asyncio.wait_for(ws.receive_json(), timeout=10)
    except Exception:
        try:
            await ws.close(code=4401, reason="auth timeout")
        except Exception:
            pass
        return
    if not isinstance(first, dict) or first.get("type") != events.EVENT_AUTH:
        await ws.close(code=4401, reason="auth required")
        return
    token = first.get("token")
    uid = decode_token(token, expected_type="access") if isinstance(token, str) else None
    if uid is None:
        await ws.close(code=4401, reason="invalid token")
        return
    user = db.get(User, uid)
    if user is None or user.status != 0:
        await ws.close(code=4401, reason="user not found")
        return
    user_id = uid

    await manager.connect(user_id, ws)
    await ws.send_json({"type": events.EVENT_AUTHED})
    try:
        while True:
            msg = await ws.receive_json()
            if isinstance(msg, dict) and msg.get("type") == events.EVENT_PING:
                await ws.send_json({"type": events.EVENT_PONG})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if user_id is not None:
            await manager.disconnect(user_id, ws)


@app.get("/healthz")
def healthz():
    """存活探针：nginx 与部署脚本用它判断服务是否正常。"""
    return {"status": "ok", "service": "channel-api", "version": settings.APP_VERSION}


@app.get("/api/v1/ping")
def ping():
    """前后端连通性测试。"""
    return {"message": "pong"}
