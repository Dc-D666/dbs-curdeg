"""成员模型（文档⑤社区成员管理，对应原生 member）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# 成员类型
MEMBER_OWNER = 0
MEMBER_ADMIN = 1
MEMBER_NORMAL = 2
MEMBER_ROBOT = 3
MEMBER_AI = 4


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (UniqueConstraint("community_id", "user_id", name="uq_member_community_user"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    nickname: Mapped[str] = mapped_column(String(64), default="")  # 频道内专属昵称
    member_type: Mapped[int] = mapped_column(Integer, default=MEMBER_NORMAL)
    join_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    join_channel: Mapped[int] = mapped_column(Integer, default=0)  # 0主动申请 1邀请加入
    shutup_expire_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_blocked: Mapped[bool] = mapped_column(default=False)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
