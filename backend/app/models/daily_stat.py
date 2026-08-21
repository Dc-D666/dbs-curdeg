"""统计周期表（文档⑲数据统计与看板管理，P0 补全）。

按日聚合：新增成员/活跃成员/帖子/互动/违规/AI 调用/留存率。
看板与报表导出基于此表；每日由定时任务写入。
"""
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DailyStat(Base):
    __tablename__ = "daily_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    new_members: Mapped[int] = mapped_column(Integer, default=0)      # 新增成员
    active_members: Mapped[int] = mapped_column(Integer, default=0)   # 活跃成员
    posts: Mapped[int] = mapped_column(Integer, default=0)            # 帖子发布量
    interactions: Mapped[int] = mapped_column(Integer, default=0)     # 互动总量(赞+评)
    violations: Mapped[int] = mapped_column(Integer, default=0)       # 违规内容数
    ai_calls: Mapped[int] = mapped_column(Integer, default=0)         # AI 调用次数
    retention: Mapped[int] = mapped_column(Integer, default=0)        # 留存率(百分数, 0-100)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
