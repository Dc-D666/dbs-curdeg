"""帖子/评论/互动相关 Pydantic 模型（阶段 3）。"""
from datetime import datetime

from pydantic import BaseModel, Field

# ---------- 请求 ----------


class CreatePostRequest(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    # 二选一：content（纯文本，兼容）或 rich_content（4.4 分片结构，优先）
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    rich_content: list | None = Field(default=None, description="4.4 分片：[{type:1,text},{type:3,url,display_text}]")
    images: list[str] = Field(default_factory=list, max_length=9)


class UpdatePostRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    rich_content: list | None = Field(default=None)
    images: list[str] | None = Field(default=None, max_length=9)


class CreateCommentRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    parent_id: int | None = Field(default=None, gt=0)  # 楼中楼：回复某条评论
    reply_to_user_id: int | None = Field(default=None, gt=0)


# ---------- 响应 ----------


class PostOut(BaseModel):
    id: int
    community_id: int
    board_id: int
    author_id: int
    title: str
    rich_content: list
    source_markdown: str
    images: list
    like_count: int
    comment_count: int
    is_top: bool
    is_essence: bool
    status: int
    created_at: datetime
    # 视图增强
    author_nickname: str = ""
    author_avatar: str = ""
    community_name: str = ""
    board_name: str = ""
    is_liked: bool = False       # 我是否点过赞
    is_followed: bool = False    # 我是否关注了该频道
    is_member: bool = False      # 我是否为频道成员（决定能否评论）

    model_config = {"from_attributes": True}


class CommentOut(BaseModel):
    id: int
    post_id: int
    author_id: int
    parent_id: int | None
    reply_to_user_id: int | None
    content: str
    like_count: int
    status: int
    created_at: datetime
    # 视图增强
    author_nickname: str = ""
    author_avatar: str = ""
    reply_to_nickname: str = ""
    is_liked: bool = False

    model_config = {"from_attributes": True}


class FeedOut(BaseModel):
    items: list[PostOut]
    next_cursor: str | None = None  # latest: "id"；hot: "like_count:id"
    has_more: bool = False


class SearchPostOut(PostOut):
    """搜索结果（阶段 4）：追加标题高亮与正文摘要。"""
    highlight_title: str = ""  # 关键词 <em class="hl"> 高亮后的标题
    snippet: str = ""          # 关键词高亮的正文摘要
