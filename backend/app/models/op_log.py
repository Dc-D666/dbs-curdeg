"""操作日志模型（阶段 4：所有管理动作留痕）。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OpLog(Base):
    __tablename__ = "op_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    operator_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # shutup/kick/block/assign_role/set_top/...
    target_type: Mapped[str] = mapped_column(String(32), default="")  # member/post/role/join_request
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, nullable=True)  # {user_id, role_id, hours, ...}
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
