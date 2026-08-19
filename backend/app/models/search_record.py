"""搜索记录模型（阶段 4：热门搜索词统计）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SearchRecord(Base):
    __tablename__ = "search_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # 游客为 NULL
    community_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # 全站搜索为 NULL
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
