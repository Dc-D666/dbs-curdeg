"""WebSocket 连接管理（阶段 5，协议见 详细开发方案.md §5.3）。

- 连接注册：user_id → set[WebSocket]（同一用户可多端/多标签在线）
- 断线清理：receive 循环捕获断开后 unregister
- 推送：send_to_user 发送 JSON 消息；发送失败静默（交给 receive 循环清理）
- 单 worker 部署（uvicorn 无 --workers），进程内直推即可；
  若将来多 worker，需改为 Redis Pub/Sub 跨进程广播（方案 D4）。
"""
import asyncio
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        """注册连接（accept 由端点负责，认证成功后才注册）。"""
        async with self._lock:
            self._connections.setdefault(user_id, set()).add(ws)

    async def disconnect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(user_id)
            if conns is None:
                return
            conns.discard(ws)
            if not conns:
                self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: int, message: dict[str, Any]) -> bool:
        """推送给该用户全部在线连接；返回是否有连接成功收到。

        发送失败视为连接已死（半开/断连连接），主动将其从 _connections 移除，
        避免依赖 receive 循环清理造成的连接泄漏。
        """
        async with self._lock:
            conns = list(self._connections.get(user_id, ()))
        sent = False
        for ws in conns:
            try:
                await ws.send_json(message)
                sent = True
            except Exception:
                # 发送失败：该连接不可用，立即清理（移除对应 user 下的该连接）
                await self.disconnect(user_id, ws)
        return sent

    async def broadcast(self, message: dict[str, Any]) -> None:
        """向所有在线连接广播（P1 ③：频道新内容实时推送）。

        单 worker 进程内广播；跨进程需 Redis Pub/Sub（方案 D4，此处未启用）。
        发送失败的连接即时清理。
        """
        async with self._lock:
            items = [(uid, ws) for uid, conns in self._connections.items() for ws in list(conns)]
        for uid, ws in items:
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(uid, ws)

    def online_count(self) -> int:
        return sum(len(v) for v in self._connections.values())


manager = ConnectionManager()
