"""AI 功能配置模型（阶段 6，文档⑰AI 能力配置管理）。

feature：assist(帮写) / review(审核) / rag(问答) / summary(摘要)
"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AiConfig(Base):
    __tablename__ = "ai_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    feature: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    model: Mapped[str] = mapped_column(String(64), default="")
    params: Mapped[dict] = mapped_column(JSON, nullable=True)  # temperature / max_tokens
    prompt_template: Mapped[str] = mapped_column(Text, default="")
    rate_limit: Mapped[int] = mapped_column(Integer, default=0)  # 0 不限制
    billing_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
