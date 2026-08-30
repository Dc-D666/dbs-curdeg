"""内容审核记录模型（阶段 6，文档⑪内容审核与巡检管理）。

流程：发帖 → AI 快审（0待审核 1通过 2驳回）→ 驳回可申诉（复审：
大 max_tokens 复审 → 驳回 / 人工复审 / 通过三态）。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

REVIEW_PENDING = 0      # 待审核
REVIEW_PASSED = 1       # 通过
REVIEW_REJECTED = 2     # 驳回（快审或复审）
REVIEW_MANUAL = 3       # 转人工复审

CONTENT_POST = 1        # 帖子
CONTENT_COMMENT = 2     # 评论


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    content_type: Mapped[int] = mapped_column(Integer, nullable=False)  # 1帖子 2评论
    content_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )  # 内容作者
    status: Mapped[int] = mapped_column(Integer, default=REVIEW_PENDING, index=True)
    violation_type: Mapped[str] = mapped_column(String(32), default="")   # 违规类型（AI 给出）
    violation_detail: Mapped[str] = mapped_column(String(255), default="")  # 违规详情
    review_method: Mapped[int] = mapped_column(Integer, default=0)  # 0AI快审 1AI复审 2人工审核
    appeal_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 申诉时间
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)   # 人工审核人
    result: Mapped[str] = mapped_column(String(255), default="")   # 处理结果
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
