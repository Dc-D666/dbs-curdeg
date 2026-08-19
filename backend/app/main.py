"""仿腾讯频道 API 入口。

模块路由：
  /api/v1/auth   账号体系（注册/登录/JWT）
  /api/v1/users  用户资料
  （后续阶段追加 community/content/interact/ai/notification）
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import auth, boards, comments, communities, interact, manage, members, posts, roles, search, topics, uploads, users
from app.core.config import settings

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


@app.get("/healthz")
def healthz():
    """存活探针：nginx 与部署脚本用它判断服务是否正常。"""
    return {"status": "ok", "service": "channel-api", "version": settings.APP_VERSION}


@app.get("/api/v1/ping")
def ping():
    """前后端连通性测试。"""
    return {"message": "pong"}
