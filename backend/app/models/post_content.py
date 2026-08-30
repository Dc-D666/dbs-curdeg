"""帖子正文（08-29 二轮审查垂直拆分：大字段与索引列解耦）。

posts 主表只保留检索/分页用的小列（title/status/计数器/外键）；正文三大件
（markdown 源文 / 富文本分片 / 图片列表）移入 1:1 扩展表：
- 主表行宽骤降 → 缓冲页容纳更多帖子行，feed keyset 扫描更快
- FULLTEXT ngram 索引随 source_markdown 迁至本表，检索走专用表
"""
from sqlalchemy import JSON, BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PostContent(Base):
    """帖子正文 1:1 扩展表；帖子删除级联清理。"""

    __tablename__ = "post_contents"

    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    # 纯文本版（检索/摘要/AI 审核用；FULLTEXT ngram 索引建在本列）
    source_markdown: Mapped[str] = mapped_column(Text, default="")
    # 富文本分片（方案 4.4 结构）：[{type:1,text}, {type:3,url,display_text}, ...]
    rich_content: Mapped[list] = mapped_column(JSON, default=list)
    images: Mapped[list] = mapped_column(JSON, default=list)  # 图片 URL 列表
