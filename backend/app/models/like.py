"""点赞模型（文档⑧点赞收藏）。

幂等设计：post_id/comment_id 用 0 表示"无"（而非 NULL）——
MySQL 唯一约束对含 NULL 的行不生效，用 0 哨兵保证 (post_id, comment_id, user_id) 唯一，
重复点赞直接撞唯一约束 → 不重复计数。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("post_id", "comment_id", "user_id", name="uq_like_target_user"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, index=True)
    comment_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
