"""Feed 排序策略模型（阶段 5，文档⑮Feed 流与排序管理）：每频道一行热度配置。

热度分公式（阶段 5）：
    score = like*weight_like + comment*weight_comment + favorite*weight_favorite
            + top_weight(置顶) ，再乘以时间衰减因子 exp(-age/decay_hours)
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

SORT_LATEST = 0  # 最新发布
SORT_HOT = 1     # 热度排序
SORT_ESSENCE = 2 # 精华优先


class FeedStrategy(Base):
    __tablename__ = "feed_strategies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    sort_rule: Mapped[int] = mapped_column(Integer, default=SORT_HOT)  # 0最新 1热度 2精华优先
    weight_like: Mapped[int] = mapped_column(Integer, default=1)
    weight_comment: Mapped[int] = mapped_column(Integer, default=2)
    weight_favorite: Mapped[int] = mapped_column(Integer, default=3)
    decay_hours: Mapped[int] = mapped_column(Integer, default=24)  # 时间衰减系数（小时）
    top_weight: Mapped[int] = mapped_column(Integer, default=100)  # 置顶帖权重
    cache_ttl: Mapped[int] = mapped_column(Integer, default=300)   # 热度缓存有效期（秒）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
