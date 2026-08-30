"""举报记录（文档⑫举报申诉管理，P0 补全）。

举报类型：1帖子 2评论 3用户 4频道；证据附件用 JSON 数组存 URL。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

REPORT_PENDING = 0    # 待处理
REPORT_PROCESSING = 1  # 处理中
REPORT_DONE = 2        # 已办结
REPORT_REJECTED = 3    # 驳回（证据不足等）

TARGET_POST = 1
TARGET_COMMENT = 2
TARGET_USER = 3
TARGET_COMMUNITY = 4


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        # 多态引用（target_type+target_id，无法挂 FK）：处理举报按目标定位
        Index("ix_reports_target", "target_type", "target_id"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    target_type: Mapped[int] = mapped_column(Integer, nullable=False)  # 1帖子 2评论 3用户 4频道
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 多态引用；单列索引由复合覆盖
    reporter_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reason_type: Mapped[str] = mapped_column(String(32), default="其他")  # 违规/侵权/垃圾信息/其他
    detail: Mapped[str] = mapped_column(String(500), default="")
    evidence: Mapped[list] = mapped_column(JSON, default=list)  # 举证附件 URL 列表
    status: Mapped[int] = mapped_column(Integer, default=REPORT_PENDING, index=True)
    result: Mapped[str] = mapped_column(String(255), default="")
    handler_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
