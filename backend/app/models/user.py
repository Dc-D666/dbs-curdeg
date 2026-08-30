"""用户账号模型（文档①用户与账号管理）。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    avatar_url: Mapped[str] = mapped_column(String(255), default="")
    bio: Mapped[str] = mapped_column(String(255), default="")
    gender: Mapped[int] = mapped_column(default=0)  # 0未知 1男 2女
    province: Mapped[str] = mapped_column(String(32), default="")
    city: Mapped[str] = mapped_column(String(32), default="")
    email: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # 手机号（优化 08-29）：应用层暂未使用 → 改可空 + 唯一约束（空值为 NULL 不参与唯一），
    # 为将来"手机号登录"预留唯一性保证。历史数据 phone='' 已由迁移清洗为 NULL。
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    status: Mapped[int] = mapped_column(default=0)  # 0正常 1封禁 2注销
    user_type: Mapped[int] = mapped_column(default=0)  # 0普通 1系统管理员 2AI虚拟账号
    # 通知开关（文档⑬）：{mention,like,comment,follow,system,review,report}
    notify_settings: Mapped[dict] = mapped_column(JSON, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_ip: Mapped[str] = mapped_column(String(45), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
