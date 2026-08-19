"""身份组模型（文档④身份组与权限管理，对应原生 role）。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="#1a73e8")
    level: Mapped[int] = mapped_column(Integer, default=0)  # 等级身份门槛（is_level_role 时：成员活跃等级 ≥ level 自动授予）
    sort: Mapped[int] = mapped_column(Integer, default=0)   # 排序/权重：越小权重越高，可管理排序在其后的身份组
    perms: Mapped[list] = mapped_column(JSON, default=list)  # 权限点集合（见方案 4.3）
    is_default: Mapped[bool] = mapped_column(default=False)
    is_level_role: Mapped[bool] = mapped_column(default=False)  # 等级身份：活跃等级达标自动授予/掉级回收
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
