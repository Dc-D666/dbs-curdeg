"""短链模型（阶段 5，文档⑭分享与短链管理）。

target_type：1频道 2帖子 3用户
访问计数：visit_count 由 Redis 定时落库（同 IP 短时间重复访问去重/限速，见 share_service）。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

TARGET_COMMUNITY = 1
TARGET_POST = 2
TARGET_USER = 3


class ShortLink(Base):
    __tablename__ = "short_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True, index=True)
    target_type: Mapped[int] = mapped_column(Integer, nullable=False)  # 1频道 2帖子 3用户
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    creator_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    visit_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
