"""加入申请模型（文档⑤辅助表：审核加入制）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# 状态
JOIN_PENDING = 0
JOIN_APPROVED = 1
JOIN_REJECTED = 2


class JoinRequest(Base):
    __tablename__ = "join_requests"
    __table_args__ = (UniqueConstraint("community_id", "user_id", name="uq_joinreq_community_user"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[int] = mapped_column(Integer, default=JOIN_PENDING)
    handler_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
