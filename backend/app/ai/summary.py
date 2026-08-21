"""帖子 AI 摘要（文档⑰"内容摘要" / 方案四 AI 摘要，P0）。

POST /ai/summary：对单篇帖子生成一句话摘要（LLM），结果不落库（课设规模直接返回）。
"""
from sqlalchemy.orm import Session

from app.core.response import NotFoundError
from app.models.post import Post, POST_STATUS_NORMAL

SUMMARY_PROMPT = (
    "你是社区内容摘要助手。用一句话（不超过 60 字）概括下面帖子的核心内容，"
    "不要输出任何前缀或引号。\n\n帖子标题：{title}\n帖子内容：{content}"
)


def summarize_post(db: Session, post_id: int) -> str:
    """生成帖子摘要。"""
    post = db.get(Post, post_id)
    if post is None or post.status != POST_STATUS_NORMAL:
        raise NotFoundError("帖子不存在")
    from app.ai import llm_gateway

    text = (post.source_markdown or "")[:1200]
    raw = llm_gateway.chat(
        [{"role": "user", "content": SUMMARY_PROMPT.format(title=post.title or "", content=text)}],
        max_tokens=120, temperature=0.3, feature="summary",
    )
    summary = (raw or "").strip()
    return summary[:120] or "暂无摘要"
