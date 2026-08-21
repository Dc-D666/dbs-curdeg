"""操作日志（阶段 4 + P0）：管理动作统一留痕 + 日志查询/导出。

log_op 支持携带 request_params / response_result（文档⑱"请求参数、响应结果"）。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.op_log import OpLog
from app.models.user import User
from app.schemas.community import OpLogOut


def log_op(
    db: Session,
    community_id: int,
    operator_id: int,
    action: str,
    target_type: str = "",
    target_id: int | None = None,
    detail: dict | None = None,
    request_params: dict | None = None,
    response_result: dict | None = None,
) -> None:
    """写一条操作日志（不 commit，由调用方事务统一提交）。"""
    db.add(
        OpLog(
            community_id=community_id,
            operator_id=operator_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            request_params=request_params,
            response_result=response_result,
        )
    )


def list_ops(
    db: Session,
    community_id: int,
    page: int,
    page_size: int,
    action: str | None = None,
    target_type: str | None = None,
    operator_id: int | None = None,
) -> dict:
    """操作日志分页（新在前，支持多条件过滤），附带操作者昵称。"""
    stmt = select(OpLog).where(OpLog.community_id == community_id)
    if action:
        stmt = stmt.where(OpLog.action == action)
    if target_type:
        stmt = stmt.where(OpLog.target_type == target_type)
    if operator_id is not None:
        stmt = stmt.where(OpLog.operator_id == operator_id)
    stmt = stmt.order_by(OpLog.id.desc())
    logs = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    total = len(db.execute(stmt.with_only_columns(OpLog.id)).scalars().all())
    operator_ids = {log.operator_id for log in logs}
    users = {}
    if operator_ids:
        users = {u.id: u for u in db.execute(select(User).where(User.id.in_(operator_ids))).scalars().all()}
    out = []
    for log in logs:
        lo = OpLogOut.model_validate(log)
        u = users.get(log.operator_id)
        if u:
            lo.operator_nickname = u.nickname or u.username
        out.append(lo)
    return {"items": out, "total": total, "page": page, "page_size": page_size}


def export_ops(
    db: Session, community_id: int, action: str | None = None, target_type: str | None = None
) -> str:
    """导出操作日志为 CSV 文本（文档⑱日志导出）。"""
    import csv
    import io

    stmt = select(OpLog).where(OpLog.community_id == community_id).order_by(OpLog.id.desc())
    if action:
        stmt = stmt.where(OpLog.action == action)
    if target_type:
        stmt = stmt.where(OpLog.target_type == target_type)
    logs = db.execute(stmt).scalars().all()
    operator_ids = {log.operator_id for log in logs}
    users = {}
    if operator_ids:
        users = {u.id: u for u in db.execute(select(User).where(User.id.in_(operator_ids))).scalars().all()}
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["时间", "操作人", "动作", "目标类型", "目标ID", "详情", "请求参数", "响应结果"])
    for log in logs:
        u = users.get(log.operator_id)
        writer.writerow([
            log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
            u.nickname or u.username if u else str(log.operator_id),
            log.action,
            log.target_type,
            log.target_id or "",
            _json_str(log.detail),
            _json_str(log.request_params),
            _json_str(log.response_result),
        ])
    return buf.getvalue()


def _json_str(v) -> str:
    """detail/request/response 转单行字符串（避免 CSV 换行破坏）。"""
    import json

    if v is None:
        return ""
    try:
        return json.dumps(v, ensure_ascii=False).replace("\n", " ")
    except (TypeError, ValueError):
        return str(v).replace("\n", " ")
