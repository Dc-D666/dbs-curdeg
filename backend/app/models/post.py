"""帖子模型（文档⑥帖子内容，对应原生 feed）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# 帖子状态
POST_STATUS_NORMAL = 0   # 正常
POST_STATUS_DELETED = 1  # 删除（软删）
POST_STATUS_BANNED = 2   # 违规下架


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        # 信息流 keyset 分页（与 post_service 真实查询一一对应，优化 08-29）：
        # 频道流   WHERE community_id=? AND status=0 AND is_top=0 ORDER BY id DESC
        # 版块流   WHERE board_id=?    AND status=0 AND is_top=0 ORDER BY id DESC
        # 全站流   WHERE status=0                          ORDER BY id DESC
        # TA的帖子 WHERE author_id=?   AND status=0        ORDER BY id DESC
        Index("ix_posts_community_status_top_id", "community_id", "status", "is_top", "id"),
        Index("ix_posts_board_status_top_id", "board_id", "status", "is_top", "id"),
        Index("ix_posts_status_id", "status", "id"),
        Index("ix_posts_author_status_id", "author_id", "status", "id"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
    )  # 单列索引被复合索引最左前缀覆盖，不再单独建
    board_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("boards.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),  # 用户不硬删（软删），RESTRICT 防误删
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(128), default="")
    post_type: Mapped[int] = mapped_column(Integer, default=0)  # 0普通 1图文 2视频 3投票
    topic_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("topics.id", ondelete="SET NULL"),  # 话题删除后帖子保留、仅解绑
        nullable=True,
        index=True,
    )
    # 正文三大件（rich_content / source_markdown / images）已垂直拆分至 post_contents
    # 1:1 扩展表（08-29 二轮审查：主表只留索引/分页小列，行宽解耦）
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)    # 浏览量（P0 补全）
    favorite_count: Mapped[int] = mapped_column(Integer, default=0)  # 收藏数（P0 补全）
    share_count: Mapped[int] = mapped_column(Integer, default=0)   # 分享数（P0 补全）
    is_top: Mapped[bool] = mapped_column(default=False)     # 置顶
    is_essence: Mapped[bool] = mapped_column(default=False)  # 精华
    # RAG 语义向量已拆分至 post_embeddings 独立表（优化 08-29）：
    # 避免高维 JSON 拉宽主表行、语义搜索不再被迫读整行帖子
    status: Mapped[int] = mapped_column(Integer, default=POST_STATUS_NORMAL)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
