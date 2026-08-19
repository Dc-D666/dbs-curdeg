"""通知相关 Pydantic 模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    actor_id: int | None = None
    actor_nickname: str = ""
    actor_avatar: str = ""
    community_id: int | None = None
    community_name: str = ""
    ref_id: int | None = None
    title: str = ""
    summary: str = ""
    is_read: bool = False
    read_at: datetime | None = None
    created_at: datetime | None = None


class NotifySettingsUpdate(BaseModel):
    """通知开关（键与 users.notify_settings 一致，见 详细开发方案.md 文档⑬）。"""

    model_config = {"extra": "forbid"}  # 未知开关键直接 400，不静默忽略

    mention: bool | None = None
    like: bool | None = None
    comment: bool | None = None
    follow: bool | None = None
    system: bool | None = None
    review: bool | None = None
    report: bool | None = None
