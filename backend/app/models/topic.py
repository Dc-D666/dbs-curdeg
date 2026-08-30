"""话题模型（文档⑪话题体系，阶段 3 收尾）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("community_id", "name", name="uq_topic_community_name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("communities.id", ondelete="CASCADE"), nullable=False
    )  # 单列索引被 uq_topic_community_name 左前缀覆盖（优化 08-29）
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")   # 话题描述（P0）
    cover_url: Mapped[str] = mapped_column(String(255), default="")     # 话题封面（P0）
    rules: Mapped[str] = mapped_column(String(500), default="")         # 话题规则（P0）
    post_count: Mapped[int] = mapped_column(Integer, default=0)         # 关联帖子数（P0）
    heat_value: Mapped[int] = mapped_column(Integer, default=0)         # 热度值（P0）
    creator_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[int] = mapped_column(Integer, default=0)  # 0正常 1删除（P0）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
