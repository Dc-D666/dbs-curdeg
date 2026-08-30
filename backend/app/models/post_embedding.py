"""帖子语义向量表（优化 08-29：从 posts.embedding JSON 列拆出）。

拆表动机：
- GLM Embedding-3 为 2048 维浮点向量，单行 JSON 约 40KB+，内联在 posts 主表
  会拉宽聚簇索引行、污染 Buffer Pool；
- 语义召回只读本表，不再为取向量扫整行帖子；
- MySQL 5.7 无向量索引（9.0 才有 VECTOR 类型），应用层余弦计算不变（课设取舍）。

写入：rag._embed_text 懒构建；读取：search_service._semantic_recall 召回。
"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PostEmbedding(Base):
    __tablename__ = "post_embeddings"

    post_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("posts.id", ondelete="CASCADE"),
        primary_key=True,  # 一帖一向量，随帖子级联删除
    )
    model: Mapped[str] = mapped_column(String(64), default="embedding-3")  # 生成模型
    vector: Mapped[list] = mapped_column(JSON, nullable=False)  # 2048 维浮点数组
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
