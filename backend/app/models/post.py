"""帖子模型（文档⑥帖子内容，对应原生 feed）。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# 帖子状态
POST_STATUS_NORMAL = 0   # 正常
POST_STATUS_DELETED = 1  # 删除（软删）
POST_STATUS_BANNED = 2   # 违规下架


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    board_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), default="")
    post_type: Mapped[int] = mapped_column(Integer, default=0)  # 0普通 1图文 2视频 3投票
    topic_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)  # 关联话题（文档⑩）
    # 富文本分片（方案 4.4 结构）：[{type:1,text}, {type:3,url,display_text}, ...]
    rich_content: Mapped[list] = mapped_column(JSON, default=list)
    # 纯文本版（检索/摘要/卡片用，阶段 5 建 FULLTEXT 索引）
    source_markdown: Mapped[str] = mapped_column(Text, default="")
    images: Mapped[list] = mapped_column(JSON, default=list)  # 图片 URL 列表
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)    # 浏览量（P0 补全）
    favorite_count: Mapped[int] = mapped_column(Integer, default=0)  # 收藏数（P0 补全）
    share_count: Mapped[int] = mapped_column(Integer, default=0)   # 分享数（P0 补全）
    is_top: Mapped[bool] = mapped_column(default=False)     # 置顶
    is_essence: Mapped[bool] = mapped_column(default=False)  # 精华
    # RAG 语义向量（阶段 6）：GLM Embedding-3 API 生成，应用层余弦相似度召回
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=POST_STATUS_NORMAL)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
