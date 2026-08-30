"""操作日志模型（阶段 4：所有管理动作留痕）。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OpLog(Base):
    __tablename__ = "op_logs"
    __table_args__ = (
        # 审计按频道+时间翻页（管理端高频，优化 08-29）
        Index("ix_op_logs_community_created", "community_id", "created_at"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("communities.id", ondelete="CASCADE"), nullable=False
    )  # 单列索引被复合索引左前缀覆盖
    operator_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # shutup/kick/block/assign_role/set_top/...
    target_type: Mapped[str] = mapped_column(String(32), default="")  # member/post/role/join_request
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, nullable=True)  # {user_id, role_id, hours, ...}
    request_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 请求参数（P0）
    response_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 响应结果（P0）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
