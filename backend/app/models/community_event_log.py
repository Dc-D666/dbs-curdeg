"""频道事件日志（运营中心数据源）。

记录频道维度的用户事件，用于频道主查看自己频道的运营数据：
  - join  加入成员
  - leave 退出成员
  - visit 访问（打点：进入频道/帖子流即记一次，去重按 (community_id, user_id) 独立访问人数）

既支持"新增成员数/退出成员数/访问人数次数"这类时序统计，
也能支撑独立用户去重（count(DISTINCT user_id)）。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# 事件类型
EVENT_JOIN = "join"
EVENT_LEAVE = "leave"
EVENT_VISIT = "visit"


class CommunityEventLog(Base):
    __tablename__ = "community_event_logs"
    __table_args__ = (
        Index("ix_ce_community_event_date", "community_id", "event", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("communities.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    event: Mapped[str] = mapped_column(String(16), nullable=False)  # join/leave/visit
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())