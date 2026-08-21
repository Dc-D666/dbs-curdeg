"""敏感词库（文档⑪"敏感词库维护 / 敏感词拦截"，P0 补全）。

发帖/评论前即时匹配：命中则直接拦截（不进入 LLM 审核队列）。
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SensitiveWord(Base):
    __tablename__ = "sensitive_words"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    category: Mapped[str] = mapped_column(String(32), default="其他")  # 涉政/涉黄/广告/诈骗/辱骂/其他
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
