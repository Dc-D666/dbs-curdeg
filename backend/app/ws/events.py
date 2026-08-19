"""WebSocket 事件定义与推送封装（阶段 5，协议见 详细开发方案.md §5.3）。

服务端 → 客户端：
  { "type": "authed" }                                        （认证成功）
  { "type": "pong" }                                          （心跳回复，30s）
  { "type": "notification", "data": {id, type, title, summary, ref_id, created_at} }

客户端 → 服务端：
  { "type": "auth", "token": "<access_token>" }               （首帧，10s 超时）
  { "type": "ping" }

同步端点（线程池）→ 主事件循环的投递方式：
  FastAPI 启动时捕获 ASGI 主循环（set_ws_loop），业务服务里调用 push_event 用
  run_coroutine_threadsafe 调度推送，线程安全。
"""
import asyncio
import logging
from typing import Any

from app.ws.manager import manager

logger = logging.getLogger(__name__)

# 事件类型（与 notifications.type 一致）
EVENT_NOTIFICATION = "notification"
EVENT_PING = "ping"
EVENT_PONG = "pong"
EVENT_AUTH = "auth"
EVENT_AUTHED = "authed"

# 通知类型
EVENT_MENTION = "mention"              # 被@
EVENT_LIKE = "like"                    # 被赞
EVENT_COMMENT = "comment"              # 新评论/回复
EVENT_FOLLOW = "follow"                # 新粉丝
EVENT_SYSTEM = "system"                # 系统通知
EVENT_REVIEW_RESULT = "review_result"  # 审核结果
EVENT_REPORT_FEEDBACK = "report_feedback"  # 举报反馈

_ws_loop: asyncio.AbstractEventLoop | None = None


def set_ws_loop(loop: asyncio.AbstractEventLoop | None) -> None:
    """记录 ASGI 主事件循环（FastAPI startup 时调用）。"""
    global _ws_loop
    _ws_loop = loop


def push_event(user_id: int, event: str, data: dict[str, Any]) -> None:
    """投递事件到主循环推送；同步/异步上下文均可调用，失败静默。"""
    loop = _ws_loop
    if loop is None or loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(
            manager.send_to_user(user_id, {"type": event, "data": data}), loop
        )
    except RuntimeError:
        pass


def notification_payload(n) -> dict[str, Any]:
    """Notification ORM → 协议 data（§5.3：id/type/title/summary/ref_id/created_at）。"""
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "summary": n.summary,
        "ref_id": n.ref_id,
        "created_at": n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else None,
    }
