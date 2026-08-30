"""AI 调用日志（文档⑰配套"调用日志查询"，P0 补全）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AiCallLog(Base):
    __tablename__ = "ai_call_logs"
    __table_args__ = (
        # 按功能统计近 N 天调用量（admin 汇总，优化 08-29）
        Index("ix_ai_call_logs_feature_created", "feature", "created_at"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    feature: Mapped[str] = mapped_column(String(32), nullable=False)  # assist/review/rag/summary/embed；单列索引由复合覆盖
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model: Mapped[str] = mapped_column(String(64), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok / degraded(主模型降级后兑底成功) / error
    error: Mapped[str] = mapped_column(String(512), default="")  # 原始错误（截断 512）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
