"""点赞模型（文档⑧点赞收藏）——08-29 二轮审查重构：likes 多态 0 哨兵表 → post_likes / comment_likes。

拆分动机：原 likes(post_id, comment_id, user_id) 用 0 哨兵区分帖子赞/评论赞，
导致两侧均无法挂外键（全库唯一例外表）。拆分后两表各自挂真外键 + 唯一约束：
- 引用完整性由 FK 级联维护（帖子/评论/用户删除自动清理点赞）
- "一人对一目标至多一赞"由 UNIQUE 在数据库层强保证（应用层先查后插 + IntegrityError 兜底）
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PostLike(Base):
    """帖子点赞：UNIQUE(post_id, user_id) 幂等；帖子/用户删除级联清理。"""

    __tablename__ = "post_likes"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_post_like_post_user"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )  # 单列点查走 uq 左前缀，不另建索引
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CommentLike(Base):
    """评论点赞：UNIQUE(comment_id, user_id) 幂等；评论/用户删除级联清理。"""

    __tablename__ = "comment_likes"
    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", name="uq_comment_like_comment_user"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    comment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("comments.id", ondelete="CASCADE"), nullable=False
    )  # 单列点查走 uq 左前缀，不另建索引
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
