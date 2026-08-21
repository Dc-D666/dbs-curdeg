"""RAG 问答（阶段 6，POST /ai/qa）：帖子 embedding（存 posts.embedding JSON 列）
+ 应用层余弦相似度召回 TopK → GLM 带引用回答。

- MySQL 5.7 无 VECTOR 类型 → JSON 数组 + Python 余弦（课设规模足够）
- 懒构建：问答时对最近的候选帖子构建 embedding（无则调 API，缓存列）
- 引用：答案末尾附 [n]《标题》来源，前端渲染可跳转

SSE 流（POST /ai/qa/stream）：搜帖 / 构建 embedding 阶段逐条推送 progress 进度，
调完 embedding 后流式输出 answer delta，最后推送 refs 引用。客户端可实时看到
"正在检索帖子的第 N 篇…" 的反馈，而不是干等。
"""
import asyncio
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


async def qa_stream(db: Session, question: str, community_id: int | None = None):
    """RAG 问答 SSE 流。yield 事件 dict：

    - {"type": "error", "message": str}         向量服务不可用
    - {"type": "progress", "stage": "search", "total": n}   已检索到候选帖子数
    - {"type": "progress", "stage": "embed", "done": i, "total": n}  已构建第 i/n 篇向量
    - {"type": "answer", "delta": str}           回答文本块（打字机效果）
    - {"type": "refs", "references": [...]}      引用列表
    """
    try:
        q_emb = await asyncio.to_thread(llm_gateway.embed, question)
    except Exception:
        logger.exception("question embed 失败")
        yield {"type": "error", "message": "向量服务不可用，请稍后再试"}
        return

    candidates = _candidates(db, community_id)
    total = len(candidates)
    logger.info("qa_stream candidates=%s question=%s", total, question)
    # 不足一篇时也告知前端（避免无任何反馈的空白等待）
    yield {"type": "progress", "stage": "search", "total": total}

    scored: list[tuple[float, Post]] = []
    for i, p in enumerate(candidates, 1):
        # embedding 构建走线程池，避免阻塞事件循环；逐篇 yield 让进度实时刷出
        emb = await asyncio.to_thread(_embed_text, p)
        if emb:
            scored.append((_cosine(q_emb, emb), p))
        yield {"type": "progress", "stage": "embed", "done": i, "total": total}

    scored.sort(key=lambda x: x[0], reverse=True)
    # 低于 MIN_SIM 阈值的候选视为不相关，不进入 TOP_K 上下文（防止噪声引入）
    top = [(s, p) for s, p in scored if s >= MIN_SIM][:TOP_K]
    await asyncio.to_thread(db.commit)  # 持久化新构建的 embedding

    if not top:
        yield {"type": "answer", "delta": "暂无可参考的帖子内容，换个问题试试。"}
        yield {"type": "refs", "references": []}
        return

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
    answer = await asyncio.to_thread(
        llm_gateway.chat, messages, "", 1024, 0.3
    )
    # 与 assist_stream 同理：GLM 推理模型流式 content 为空，故一次性取回再切块模拟流式
    step = 8
    for i in range(0, len(answer), step):
        yield {"type": "answer", "delta": answer[i:i + step]}
    yield {"type": "refs", "references": [{"id": p.id, "title": p.title} for _, p in top]}
