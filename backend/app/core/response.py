"""统一响应与业务异常（见 详细开发方案.md §5.1）。

HTTP 状态码与 body code 并存：
  400 + 2001 参数错误
  401 + 1001 token 失效 / 未登录
  403 + 1002 无权限
  404 + 2004 资源不存在
  409 + 2002 冲突（如用户名/邮箱已存在）
  429 + 3001 限流
"""
from typing import Any

from fastapi import HTTPException, status


class BizError(HTTPException):
    """业务异常：携带业务 code。"""

    def __init__(self, code: int, message: str, http_status: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=http_status, detail=message)
        self.biz_code = code


# 常用业务错误
class AuthError(BizError):
    def __init__(self, message: str = "登录已失效，请重新登录"):
        super().__init__(code=1001, message=message, http_status=status.HTTP_401_UNAUTHORIZED)


class PermissionError_(BizError):
    def __init__(self, message: str = "无权限执行该操作"):
        super().__init__(code=1002, message=message, http_status=status.HTTP_403_FORBIDDEN)


class NotFoundError(BizError):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(code=2004, message=message, http_status=status.HTTP_404_NOT_FOUND)


class ConflictError(BizError):
    def __init__(self, message: str = "资源冲突"):
        super().__init__(code=2002, message=message, http_status=status.HTTP_409_CONFLICT)


class ParamError(BizError):
    def __init__(self, message: str = "参数错误"):
        super().__init__(code=2001, message=message)


class FeatureDisabledError(BizError):
    """AI 功能被管理端关闭（ai_configs.enabled=0；08-29 整改：让管理端开关真正生效）。"""

    def __init__(self, message: str = "该 AI 功能已被管理员关闭"):
        super().__init__(code=2003, message=message, http_status=status.HTTP_403_FORBIDDEN)


def ok(data: Any = None, message: str = "ok") -> dict:
    """统一成功响应。"""
    return {"code": 0, "message": message, "data": data}
