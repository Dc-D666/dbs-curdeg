"""收藏模型（文档⑨收藏记录，P0 补全）。

幂等： (user_id, post_id) 唯一，重复收藏撞唯一约束。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_fav_user_post"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )  # 单列索引被 uq_fav_user_post 左前缀覆盖（优化 08-29）
    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_name: Mapped[str] = mapped_column(String(32), default="默认")  # 收藏分组
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
