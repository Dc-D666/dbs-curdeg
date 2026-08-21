"""AI 调用日志服务（文档⑰配套"调用日志查询"，P0）。

llm_gateway.chat/embed 内部自动埋点：每次调用独立开 Session 写一条记录，
失败不影响主流程（写日志异常静默）。
"""
import logging
import time

logger = logging.getLogger(__name__)


def log_ai_call(
    feature: str,
    user_id: int | None,
    model: str,
    latency_ms: int,
    status: str = "ok",
    error: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """写一条 AI 调用日志（独立 Session，失败静默）。"""
    try:
        from app.db import SessionLocal
        from app.models.ai_call_log import AiCallLog

        db = SessionLocal()
        try:
            db.add(
                AiCallLog(
                    feature=feature[:32],
                    user_id=user_id,
                    model=model[:64],
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=latency_ms,
                    status=status[:16],
                    error=error[:255],
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("AI 调用日志写入失败 feature=%s", feature)


def query_logs(
    db, feature: str | None, status: str | None, page: int, page_size: int
) -> dict:
    """AI 调用日志查询（管理端，可按功能/状态过滤）。"""
    from sqlalchemy import func, select

    from app.models.ai_call_log import AiCallLog

    stmt = select(AiCallLog)
    if feature:
        stmt = stmt.where(AiCallLog.feature == feature)
    if status:
        stmt = stmt.where(AiCallLog.status == status)
    stmt = stmt.order_by(AiCallLog.id.desc())
    total = db.execute(stmt.with_only_columns(func.count(AiCallLog.id))).scalar_one()
    items = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return {
        "items": [
            {
                "id": r.id, "feature": r.feature, "user_id": r.user_id, "model": r.model,
                "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens,
                "latency_ms": r.latency_ms, "status": r.status, "error": r.error,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
            }
            for r in items
        ],
        "total": total, "page": page, "page_size": page_size,
    }


def summary(db, days: int = 7) -> dict:
    """AI 调用汇总（近 N 天）：按功能统计调用次数。"""
    from datetime import datetime, timedelta

    from sqlalchemy import func, select

    from app.models.ai_call_log import AiCallLog

    since = datetime.now() - timedelta(days=days)
    rows = db.execute(
        select(AiCallLog.feature, func.count(AiCallLog.id))
        .where(AiCallLog.created_at >= since)
        .group_by(AiCallLog.feature)
    ).all()
    return {"days": days, "features": [{"feature": f, "count": c} for f, c in rows]}
