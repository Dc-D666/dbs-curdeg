"""评论模型（文档⑦评论，楼中楼：parent_id 为空 = 顶层评论；非空 = 对该评论的回复（一级嵌套））。"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        # 评论列表/楼中楼 keyset 分页（与 comment_service 真实查询对应，优化 08-29）：
        # 顶层   WHERE post_id=? AND parent_id IS NULL AND status=0 ORDER BY id
        # 楼中楼 WHERE parent_id=? AND status=0 ORDER BY id
        Index("ix_comments_post_status_id", "post_id", "status", "id"),
        Index("ix_comments_parent_status_id", "parent_id", "status", "id"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
    )  # 单列索引被复合索引覆盖
    author_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
    )  # 单列索引被复合索引覆盖
    reply_to_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(String(2000), nullable=False)
    comment_type: Mapped[int] = mapped_column(Integer, default=0)  # 0普通 1回复 2@提及（P0 补全）
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)   # 楼中楼回复数（P0 补全）
    ip_region: Mapped[str] = mapped_column(String(64), default="")  # IP 属地（P0 补全）
    status: Mapped[int] = mapped_column(Integer, default=0)  # 0正常 1删除（软删）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
