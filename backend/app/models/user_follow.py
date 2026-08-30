"""用户互关模型（文档⑨"关注目标类型（用户/频道）"，P0 补全用户侧）。

频道关注走 follows 表（保持线上数据不变），用户互关独立成表，
避免改动 follows 既有约束。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserFollow(Base):
    __tablename__ = "user_follows"
    __table_args__ = (UniqueConstraint("user_id", "target_user_id", name="uq_ufollow_uv"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )  # 关注者；单列索引被 uq_ufollow_uv 左前缀覆盖（优化 08-29）
    target_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )  # 被关注者
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
