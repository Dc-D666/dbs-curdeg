"""RAG 问答（阶段 6，POST /ai/qa）：帖子 embedding（存 posts.embedding JSON 列）
+ 应用层余弦相似度召回 TopK → GLM 带引用回答。

- MySQL 5.7 无 VECTOR 类型 → JSON 数组 + Python 余弦（课设规模足够）
- 懒构建：问答时对最近的候选帖子构建 embedding（无则调 API，缓存列）
- 引用：答案末尾附 [n]《标题》来源，前端渲染可跳转
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import llm_gateway
from app.models.post import Post, POST_STATUS_NORMAL

logger = logging.getLogger(__name__)

EMBED_TEXT_LIMIT = 2000   # 入向量文本截断
CANDIDATE_LIMIT = 30      # 懒构建候选帖子数（首问时逐篇调 embedding API）
MIN_SIM = 0.2             # 最小相似度阈值：低于此值的候选不进入 TOP_K 上下文
TOP_K = 5


def _embed_text(post: Post) -> list[float] | None:
    """取帖子向量（已缓存直接用；否则调 API 并缓存到列）。"""
    if post.embedding:
        return post.embedding
    text = f"{post.title}\n{post.source_markdown or ''}"[:EMBED_TEXT_LIMIT]
    if not text.strip():
        return None
    try:
        emb = llm_gateway.embed(text)
    except Exception:
        logger.exception("embedding 构建失败 post_id=%s", post.id)
        return None
    post.embedding = emb
    return emb


def _cosine(a: list[float], b: list[float]) -> float:
    import math

    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def _candidates(db: Session, community_id: int | None) -> list[Post]:
    """候选帖子：最近 N 篇（懒构建对象），可选频道过滤。"""
    stmt = (
        select(Post)
        .where(Post.status == POST_STATUS_NORMAL)
        .order_by(Post.id.desc())
        .limit(CANDIDATE_LIMIT)
    )
    if community_id:
        stmt = stmt.where(Post.community_id == community_id)
    return list(db.execute(stmt).scalars().all())


def qa(db: Session, question: str, community_id: int | None = None) -> dict:
    """问答：返回 {answer, references:[{id,title}]}。"""
    try:
        q_emb = llm_gateway.embed(question)
    except Exception:
        raise RuntimeError("向量服务不可用，请稍后再试") from None

    scored = []
    for p in _candidates(db, community_id):
        emb = _embed_text(p)
        if emb:
            scored.append((_cosine(q_emb, emb), p))
    scored.sort(key=lambda x: x[0], reverse=True)
    # 低于 MIN_SIM 阈值的候选视为不相关，不进入 TOP_K 上下文（防止噪声引入）
    top = [(s, p) for s, p in scored if s >= MIN_SIM][:TOP_K]
    db.commit()  # 持久化新构建的 embedding

    if not top:
        return {"answer": "暂无可参考的帖子内容，换个问题试试。", "references": []}

    context = "\n".join(
        f"[{i + 1}]《{p.title}》(id={p.id}): {(p.source_markdown or '')[:300]}"
        for i, (_, p) in enumerate(top)
    )
    messages = [
        {
            "role": "system",
            "content": "你是频道社区问答机器人。根据提供的帖子内容回答用户问题；"
                       "回答中引用来源时用 [n] 标注（如「根据帖子[1]」）；"
                       "若内容不足以回答，请如实说明。只输出回答正文。",
        },
        {"role": "user", "content": f"问题：{question}\n\n参考帖子：\n{context}"},
    ]
    answer = llm_gateway.chat(messages, max_tokens=1024, temperature=0.3)
    return {
        "answer": answer,
        "references": [{"id": p.id, "title": p.title} for _, p in top],
    }
