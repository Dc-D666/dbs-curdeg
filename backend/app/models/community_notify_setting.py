"""频道级通知设置（频道设置页「消息接收类型」）。

用户可对单个频道覆盖其通知开关（mention/like/comment/follow/review/report/system），
未配置的频道继承全局 users.notify_settings。
"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CommunityNotifySetting(Base):
    __tablename__ = "community_notify_settings"
    __table_args__ = (
        UniqueConstraint("community_id", "user_id", name="uq_community_notify_user"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("communities.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # 与全局 keys 一致：mention/like/comment/follow/system/review/report
    settings: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )