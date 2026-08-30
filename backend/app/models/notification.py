"""通知消息模型（阶段 5，文档⑬通知消息管理）。

type 取值：mention(被@) / like(被赞) / comment(新评论/回复) / follow(新粉丝) /
          system(系统通知) / review_result(审核结果) / report_feedback(举报反馈)

ref_id 约定（前端据此跳转）：帖子相关事件 → post_id；频道相关事件 → community_id。
ref_type（08-29 补）：显式声明 ref_id 指向的实体类型 post/comment/community/user，
消除"type → ref_id 含义"的隐式约定（report_feedback 等多态场景无约定可言）。
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )  # 接收者；单列索引被 ix_notifications_user_read 左前缀覆盖（优化 08-29）
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # 见模块 docstring
    actor_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )  # 触发者（系统通知可空）
    community_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("communities.id", ondelete="CASCADE"), nullable=True
    )  # 所在频道
    ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # 关联内容 ID（见约定）
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # ref_id 指向的实体类型：post/comment/community/user
    title: Mapped[str] = mapped_column(String(128), default="")
    summary: Mapped[str] = mapped_column(String(255), default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        # 未读列表高频查询：按用户 + 未读 + 时间倒序
        # 与迁移 a1b2c3d4e5f6 中的 ix_notifications_user_read(user_id, is_read, id) 保持一致
        Index("ix_notifications_user_read", "user_id", "is_read", "id"),
        {"mysql_engine": "InnoDB"},
    )
