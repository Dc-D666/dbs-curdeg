"""AI 接口（阶段 6 + P0）：帮写（SSE）/ 问答（RAG）/ 摘要 / 绘画 / 频道助手 / 审核与申诉。"""
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import assist, rag, review, summary
from app.core.deps import get_current_user
from app.core.ratelimit import rate_limit
from app.core.response import NotFoundError, ParamError, ok
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

    # X-Accel-Buffering: no 让 nginx 关闭 response buffering，逐事件实时转发到浏览器，
    # 否则 nginx 会把整个 SSE 缓冲到结束才一次吐给前端，看不到流式/进度。
    return StreamingResponse(
        wrapper(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse_events(gen) -> StreamingResponse:
    """通用 SSE：yield 任意事件 dict，原样序列化为 data: {...json...} 行。"""
    import json

    async def wrapper():
        async for event in gen:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        wrapper(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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


@router.post("/qa/stream", dependencies=[Depends(rate_limit("ai_qa", limit=20, window=60))])
async def ai_qa_stream(
    payload: QARequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """RAG 问答 SSE 流：搜帖 / 构建 embedding 时实时推送进度，再流式输出回答。"""
    return _sse_events(rag.qa_stream(db, payload.question, payload.community_id))


class SummaryRequest(BaseModel):
    post_id: int = Field(gt=0)


@router.post("/summary", dependencies=[Depends(rate_limit("ai_summary", limit=20, window=60))])
def ai_summary(
    payload: SummaryRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """帖子 AI 摘要（P0 文档⑰内容摘要）。"""
    return ok(data={"summary": summary.summarize_post(db, payload.post_id)})


class DrawRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)


@router.post("/draw", dependencies=[Depends(rate_limit("ai_draw", limit=10, window=60))])
def ai_draw(
    payload: DrawRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI 绘画入口（P0 文档四：发帖编辑器"文生图"）。

    需在系统配置中设置 draw_api_url / draw_api_key（兼容 OpenAI 图片接口），
    未配置时返回明确提示（不发真实请求）。
    """
    from app.services import system_config_service

    draw_url = system_config_service.get(db, "draw_api_url")
    draw_key = system_config_service.get(db, "draw_api_key")
    if not draw_url or not draw_key:
        raise ParamError("AI 绘画服务未配置，请联系管理员开启")
    try:
        import requests

        resp = requests.post(
            draw_url,
            headers={"Authorization": f"Bearer {draw_key}"},
            json={
                "model": system_config_service.get(db, "draw_api_model") or "flux",
                "prompt": payload.prompt,
                "n": 1,
                "size": "1024x1024",
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        # OpenAI 图片接口风格：data[].url 或 data[].b64_json
        img = data["data"][0]
        return ok(data={"url": img.get("url") or "", "b64_json": img.get("b64_json") or ""})
    except Exception as e:
        raise ParamError(f"AI 绘画调用失败：{e}") from e


class AssistantCreateRequest(BaseModel):
    nickname: str = Field(default="频道助手", max_length=32)


@router.post("/communities/{community_id}/ai-assistant")
def ai_assistant_ensure(
    community_id: int,
    payload: AssistantCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建/获取频道 AI 助手虚拟成员（member.type=ai，P0 文档四"频道助手"）。

    幂等：每个频道一个 AI 虚拟账号（user_type=2）+ member(member_type=4)，
    前端可在发帖/评论中 @ 触发问答。
    """
    from app.models.member import MEMBER_AI, Member
    from app.services.post_service import _require_member

    _require_member(db, community_id, user.id)
    # 取该频道已有的 AI 助手成员
    existing = db.execute(
        select(Member).where(Member.community_id == community_id, Member.member_type == MEMBER_AI)
    ).scalar_one_or_none()
    if existing:
        ai_user = db.get(User, existing.user_id)
        return ok(data={
            "member_id": existing.id,
            "user_id": existing.user_id,
            "nickname": ai_user.nickname if ai_user else existing.nickname,
            "avatar_url": ai_user.avatar_url if ai_user else "",
        })
    # 创建/复用 AI 虚拟账号（按昵称全局唯一）
    nickname = payload.nickname.strip() or "频道助手"
    ai_user = db.execute(
        select(User).where(User.user_type == 2, User.username == f"ai_{community_id}")
    ).scalar_one_or_none()
    if ai_user is None:
        from app.core.security import hash_password

        ai_user = User(
            username=f"ai_{community_id}",
            nickname=nickname,
            email=f"ai_{community_id}@internal.local",
            password_hash=hash_password("ai-assistant-not-for-login"),
            user_type=2,  # AI 虚拟账号
            bio="本频道的 AI 助手，可在发帖中 @ 触发问答",
        )
        db.add(ai_user)
        db.flush()
    member = Member(
        community_id=community_id,
        user_id=ai_user.id,
        nickname=nickname,
        member_type=MEMBER_AI,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return ok(data={
        "member_id": member.id,
        "user_id": ai_user.id,
        "nickname": ai_user.nickname,
        "avatar_url": ai_user.avatar_url,
    }, message="频道助手已就位")


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
