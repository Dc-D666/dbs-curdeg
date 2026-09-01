"""计数器对账台账模型（数据一致性证据链，阶段 5）。

仅由数据库触发器写入（trg_*_ai/ad），记录每次计数增量，供
sp_reconcile_counters 前的可查证据链；也被 ev_reconcile_counters
定时清理 90 天前的历史。ORM 模型用于 Alembic autogenerate 感知该表
（避免 autogenerate 把"库里存在但无模型"的表判为待删）。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CounterAudit(Base):
    __tablename__ = "counter_audit"
    __table_args__ = (
        Index("ix_counter_audit_col_target", "col", "target_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tbl: Mapped[str] = mapped_column(String(32), nullable=False, comment="来源表")
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="计数器所属父行 ID")
    col: Mapped[str] = mapped_column(String(64), nullable=False, comment="受影响计数列")
    delta: Mapped[int] = mapped_column(Integer, nullable=False, comment="增量")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
