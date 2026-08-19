"""操作日志（阶段 4）：管理动作统一留痕 + 日志查询。"""
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
        )
    )


def list_ops(db: Session, community_id: int, page: int, page_size: int) -> dict:
    """操作日志分页（新在前），附带操作者昵称。"""
    stmt = (
        select(OpLog)
        .where(OpLog.community_id == community_id)
        .order_by(OpLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = db.execute(stmt).scalars().all()
    total = len(
        db.execute(select(OpLog.id).where(OpLog.community_id == community_id)).scalars().all()
    )
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
