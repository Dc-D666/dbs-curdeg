"""搜索服务（阶段 4）：关键词 FULLTEXT(ngram) + LIKE 兜底 + 高亮 + 热门词。

召回策略：
  1. 优先 FULLTEXT MATCH...AGAINST（生产库有 ngram 索引，中文分词友好）；
  2. MATCH 不可用（测试库 create_all 无 FULLTEXT 索引）或召回为空 → LIKE %kw% 兜底；
  3. 两路结果按 id 去重合并，再分页；
  4. 每次搜索写 search_records（热门词统计来源）。

语义召回（embedding 余弦双路融合）为阶段 6 挂点：_semantic_recall() 默认返回空。
"""
import html
from datetime import datetime, timedelta

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.core.response import ParamError
from app.models.community import Community
from app.models.post import Post, POST_STATUS_NORMAL
from app.models.search_record import SearchRecord
from app.schemas.post import SearchPostOut

HOT_WINDOW_DAYS = 7
HOT_LIMIT = 10
_MATCH_MAX = 60  # 单路召回放大上限，合并后统一分页


def search_posts(
    db: Session,
    q: str,
    page: int,
    page_size: int,
    current_user_id: int | None = None,
    community_id: int | None = None,
) -> dict:
    """关键词搜索帖子（公开，游客可用）。"""
    q = (q or "").strip()
    if not q:
        raise ParamError("搜索关键词不能为空")
    if len(q) > 64:
        raise ParamError("搜索关键词过长")

    if community_id is not None:
        community = db.get(Community, community_id)
        if community is None or community.status != 0:
            raise ParamError("频道不存在")

    # 双路召回：FULLTEXT 优先，LIKE 兜底，按 id 去重合并
    merged: list[int] = []
    seen: set[int] = set()
    for pid in _fulltext_ids(db, q, community_id):
        if pid not in seen:
            seen.add(pid)
            merged.append(pid)
    for post in _like_posts(db, q, community_id):
        if post.id not in seen:
            seen.add(post.id)
            merged.append(post.id)

    # 语义召回（阶段 7）：embedding 余弦补漏（关键词命中优先，语义只补召回缺口）
    for pid in _semantic_recall(db, q, community_id):
        if pid not in seen:
            seen.add(pid)
            merged.append(pid)

    total = len(merged)
    page_ids = merged[(page - 1) * page_size: page * page_size]
    posts = []
    if page_ids:
        posts = db.execute(
            select(Post).where(Post.id.in_(page_ids), Post.status == POST_STATUS_NORMAL)
        ).scalars().all()
        by_id = {p.id: p for p in posts}
        posts = [by_id[i] for i in page_ids if i in by_id]

    # 语义召回挂点（阶段 6 接入 embedding 后融合）
    # semantic_ids = _semantic_recall(db, q, community_id)

    items = _search_outs(db, posts, q)

    # 记录搜索词（热门词统计）
    db.add(
        SearchRecord(
            keyword=q[:64],
            user_id=current_user_id,
            community_id=community_id,
        )
    )
    db.commit()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < total,
    }


def hot_keywords(db: Session, limit: int = HOT_LIMIT) -> list[dict]:
    """热门搜索词：近 7 天按次数倒序。"""
    since = datetime.now() - timedelta(days=HOT_WINDOW_DAYS)
    rows = db.execute(
        text(
            "SELECT keyword, COUNT(*) AS cnt FROM search_records "
            "WHERE created_at >= :since GROUP BY keyword ORDER BY cnt DESC, keyword LIMIT :limit"
        ),
        {"since": since, "limit": limit},
    ).all()
    return [{"keyword": r[0], "count": r[1]} for r in rows]


# ---------- 召回 ----------


def _fulltext_ids(db: Session, q: str, community_id: int | None) -> list[int]:
    """FULLTEXT MATCH...AGAINST（ngram 解析器）；无索引（测试库）时静默降级。"""
    sql = (
        "SELECT id FROM posts "
        "WHERE MATCH(title, source_markdown) AGAINST (:q IN NATURAL LANGUAGE MODE) AND status = 0"
    )
    params: dict = {"q": q}
    if community_id is not None:
        sql += " AND community_id = :cid"
        params["cid"] = community_id
    sql += " ORDER BY id DESC LIMIT :limit"
    params["limit"] = _MATCH_MAX
    try:
        rows = db.execute(text(sql), params).scalars().all()
        return list(rows)
    except Exception:
        # 无 FULLTEXT 索引（如测试库 create_all）→ 交给 LIKE 兜底
        return []


def _like_posts(db: Session, q: str, community_id: int | None) -> list[Post]:
    """LIKE 兜底召回（title / source_markdown 模糊匹配）。"""
    escaped = (
        q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    like = f"%{escaped}%"
    stmt = (
        select(Post)
        .where(
            Post.status == POST_STATUS_NORMAL,
            or_(Post.title.like(like), Post.source_markdown.like(like)),
        )
        .order_by(Post.id.desc())
        .limit(_MATCH_MAX)
    )
    if community_id is not None:
        stmt = stmt.where(Post.community_id == community_id)
    return list(db.execute(stmt).scalars().all())


def _semantic_recall(db: Session, q: str, community_id: int | None) -> list[int]:
    """语义召回（阶段 7）：query embedding → 已构建 embedding 的帖子余弦 TopK。

    只召回过 embedding 的帖子（不在此处懒构建，避免搜索链路调外部 API）；
    需要先通过问答/其他路径构建（posts.embedding 列）。GLM 不可用或相似度
    低于阈值时返回空（不影响关键词路径）。
    """
    from app.ai import llm_gateway
    from app.ai.rag import _cosine

    try:
        q_emb = llm_gateway.embed(q)
    except Exception:
        return []
    stmt = (
        select(Post)
        .where(Post.status == POST_STATUS_NORMAL, Post.embedding.is_not(None))
        .order_by(Post.id.desc())
        .limit(50)
    )
    if community_id is not None:
        stmt = stmt.where(Post.community_id == community_id)
    scored = []
    for p in db.execute(stmt).scalars().all():
        score = _cosine(q_emb, p.embedding)
        if score > 0.5:
            scored.append((score, p.id))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [pid for _, pid in scored[:20]]


# ---------- 组装与高亮 ----------


def _search_outs(db: Session, posts: list[Post], q: str) -> list[SearchPostOut]:
    """组装搜索结果：复用 PostOut 视图增强 + 标题/摘要高亮。"""
    from app.services.post_service import post_outs

    if not posts:
        return []
    base = post_outs(db, posts, None)
    out = []
    for b in base:
        o = SearchPostOut.model_validate(b.model_dump())
        o.highlight_title = highlight(b.title, q)
        o.snippet = make_snippet(b.source_markdown, q)
        out.append(o)
    return out


def highlight(text: str, q: str) -> str:
    """把关键词出现处包上 <em class="hl">（HTML 转义后操作）。"""
    if not text or not q:
        return html.escape(text or "")
    escaped = html.escape(text)
    # 关键词本身转义后做替换（不区分大小写）
    kw = html.escape(q)
    lower = escaped.lower()
    parts = []
    start = 0
    while True:
        idx = lower.find(kw.lower(), start)
        if idx < 0:
            parts.append(escaped[start:])
            break
        parts.append(escaped[start:idx])
        parts.append(f'<em class="hl">{escaped[idx:idx + len(kw)]}</em>')
        start = idx + len(kw)
    return "".join(parts)


def make_snippet(text: str, q: str, length: int = 80) -> str:
    """以首个关键词命中处为中心截取摘要。"""
    if not text:
        return ""
    low = text.lower()
    idx = low.find(q.lower())
    if idx < 0:
        return html.escape(text[:length])
    start = max(0, idx - length // 2)
    end = min(len(text), start + length)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + highlight(text[start:end], q) + suffix
