"""AI 接口（阶段 6）：帮写（SSE 流式）/ 问答（RAG）/ 审核记录与申诉。"""
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import assist, rag, review
from app.core.deps import get_current_user
from app.core.ratelimit import rate_limit
from app.core.response import ok
from app.db import get_db
from app.models.review import Review
from app.models.user import User

router = APIRouter(prefix="/ai", tags=["ai"])


class AssistRequest(BaseModel):
    action: str = Field(default="write", pattern="^(write|polish|title)$")
    title: str = Field(default="", max_length=128)
    content: str = Field(default="", max_length=5000)


class QARequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    community_id: int | None = Field(default=None, gt=0)


def _sse_stream(gen) -> StreamingResponse:
    """把（异步）文本块迭代器包装成 SSE 流（data: {json} 格式）。"""
    import json

    async def wrapper():
        async for chunk in gen:
            yield f"data: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(wrapper(), media_type="text/event-stream")


@router.post("/assist", dependencies=[Depends(rate_limit("ai_assist", limit=20, window=60))])
async def ai_assist(
    payload: AssistRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """AI 帮写/润色/起标题（SSE 流式，前端打字机效果）。"""
    return _sse_stream(assist.assist_stream(payload, request))


@router.post("/qa", dependencies=[Depends(rate_limit("ai_qa", limit=20, window=60))])
def ai_qa(
    payload: QARequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """RAG 问答：帖子语义召回 + LLM 带引用回答。"""
    try:
        return ok(data=rag.qa(db, payload.question, payload.community_id), message="ok")
    except RuntimeError as e:
        return ok(data={"answer": str(e), "references": []})


@router.get("/reviews/me")
def my_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的内容审核记录。"""
    stmt = select(Review).where(Review.user_id == user.id).order_by(Review.id.desc())
    total = len(db.execute(stmt.with_only_columns(Review.id)).scalars().all())
    items = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return ok(data={
        "items": [_review_out(r) for r in items],
        "total": total, "page": page, "page_size": page_size,
    })


@router.post("/reviews/{review_id}/appeal", dependencies=[Depends(rate_limit("ai_appeal", limit=20, window=60))])
def appeal_review(
    review_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """申诉被驳回的内容 → AI 复审（通过/驳回/转人工）。"""
    r = review.appeal(db, user, review_id)
    return ok(data=_review_out(r), message="申诉已受理")


def _review_out(r: Review) -> dict:
    return {
        "id": r.id,
        "content_type": r.content_type,
        "content_id": r.content_id,
        "status": r.status,
        "violation_type": r.violation_type,
        "violation_detail": r.violation_detail,
        "review_method": r.review_method,
        "appeal_at": r.appeal_at.strftime("%Y-%m-%d %H:%M:%S") if r.appeal_at else None,
        "result": r.result,
        "reviewed_at": r.reviewed_at.strftime("%Y-%m-%d %H:%M:%S") if r.reviewed_at else None,
        "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
    }
