"""版块模型（文档③版块分区管理，对应原生 channel）。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Board(Base):
    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)
    allow_post_role_ids: Mapped[list] = mapped_column(JSON, default=list)  # 允许发帖身份组
    allow_anonymous: Mapped[bool] = mapped_column(default=False)
    status: Mapped[int] = mapped_column(Integer, default=0)  # 0正常 1隐藏 2关闭
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
