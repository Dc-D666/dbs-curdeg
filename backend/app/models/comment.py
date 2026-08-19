"""评论模型（文档⑦评论互动，对应原生 comment）。

楼中楼：parent_id 为空 = 顶层评论；非空 = 对该评论的回复（一级嵌套）。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    reply_to_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content: Mapped[str] = mapped_column(String(2000), nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=0)  # 0正常 1删除（软删）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
