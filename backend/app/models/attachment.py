"""帖子媒体附件模型（文档⑦帖子媒体附件管理，P0 补全）。

与 posts.images(URL 数组) 不同：附件表记录完整媒体元数据
（尺寸/大小/时长/排序），支持列表与删除。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ATTACH_IMAGE = 1
ATTACH_VIDEO = 2
ATTACH_FILE = 3


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    media_type: Mapped[int] = mapped_column(Integer, default=ATTACH_IMAGE)  # 1图片 2视频 3文件
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    thumb_url: Mapped[str] = mapped_column(String(255), default="")   # 缩略图/封面
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    file_size: Mapped[int] = mapped_column(Integer, default=0)         # 字节
    duration: Mapped[int] = mapped_column(Integer, default=0)          # 视频时长(秒)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
