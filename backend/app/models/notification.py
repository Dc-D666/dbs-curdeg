"""通知消息模型（阶段 5，文档⑬通知消息管理）。

type 取值：mention(被@) / like(被赞) / comment(新评论/回复) / follow(新粉丝) /
          system(系统通知) / review_result(审核结果) / report_feedback(举报反馈)

ref_id 约定（前端据此跳转）：帖子相关事件 → post_id；频道相关事件 → community_id。
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)  # 接收者
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # 见模块 docstring
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # 触发者（系统通知可空）
    community_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # 所在频道
    ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # 关联内容 ID（见约定）
    title: Mapped[str] = mapped_column(String(128), default="")
    summary: Mapped[str] = mapped_column(String(255), default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        # 未读列表高频查询：按用户 + 未读 + 时间倒序
        {"mysql_engine": "InnoDB"},
    )
