"""举报业务（文档⑫举报申诉管理，P0）。

流程：用户提交举报（帖子/评论/用户/频道）→ 管理员受理/办结/驳回 → 结果通知举报人。
状态：0待处理 1处理中 2已办结 3驳回。
"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.response import NotFoundError, ParamError, PermissionError_
from app.models.comment import Comment
from app.models.community import Community
from app.models.post import Post, POST_STATUS_NORMAL
from app.models.report import (
    REPORT_DONE,
    REPORT_PENDING,
    REPORT_PROCESSING,
    REPORT_REJECTED,
    TARGET_COMMENT,
    TARGET_COMMUNITY,
    TARGET_POST,
    TARGET_USER,
    Report,
)
from app.models.user import User
from app.services.notify_service import notify


def create_report(
    db: Session,
    reporter: User,
    target_type: int,
    target_id: int,
    reason_type: str,
    detail: str,
    evidence: list[str],
) -> Report:
    """提交举报（目标须存在；同一用户对同一目标存在未办结举报时拒绝重复提交）。"""
    _check_target(db, target_type, target_id)
    duplicate = db.execute(
        select(Report.id).where(
            Report.reporter_id == reporter.id,
            Report.target_type == target_type,
            Report.target_id == target_id,
            Report.status.in_((REPORT_PENDING, REPORT_PROCESSING)),
        )
    ).scalar_one_or_none()
    if duplicate:
        raise ParamError("你已举报过该内容，请等待处理结果")
    report = Report(
        target_type=target_type,
        target_id=target_id,
        reporter_id=reporter.id,
        reason_type=(reason_type or "其他")[:32],
        detail=detail[:500],
        evidence=evidence[:9],
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def list_reports(db: Session, status: int | None, page: int, page_size: int) -> dict:
    """举报记录分页（管理端，可过滤状态）。"""
    stmt = select(Report).order_by(Report.id.desc())
    conditions = []
    if status is not None:
        conditions.append(Report.status == status)
        stmt = stmt.where(Report.status == status)
    total = db.execute(
        select(func.count(Report.id)).where(*conditions)
    ).scalar_one()
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return {
        "items": _reports_out(db, rows),
        "total": total, "page": page, "page_size": page_size,
    }


def list_my_reports(db: Session, reporter_id: int, page: int, page_size: int) -> dict:
    """我的举报记录。"""
    total = db.execute(
        select(func.count(Report.id)).where(Report.reporter_id == reporter_id)
    ).scalar_one()
    rows = db.execute(
        select(Report)
        .where(Report.reporter_id == reporter_id)
        .order_by(Report.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return {
        "items": _reports_out(db, rows),
        "total": total, "page": page, "page_size": page_size,
    }


def handle_report(
    db: Session, handler: User, report_id: int, action: str, result: str = ""
) -> Report:
    """管理员处理举报：processing 受理 / done 办结 / rejected 驳回。"""
    report = db.get(Report, report_id)
    if report is None:
        raise NotFoundError("举报记录不存在")
    action = action.lower()
    if action == "processing":
        report.status = REPORT_PROCESSING
        msg = "你的举报已受理，正在处理中"
    elif action == "done":
        report.status = REPORT_DONE
        report.result = result or "已处理"
        report.handled_at = datetime.now()
        report.handler_id = handler.id
        msg = "你提交的举报已办结"
    elif action == "rejected":
        report.status = REPORT_REJECTED
        report.result = result or "证据不足，举报被驳回"
        report.handled_at = datetime.now()
        report.handler_id = handler.id
        msg = "你提交的举报经核实证据不足，已驳回"
    else:
        raise ParamError("action 仅支持 processing/done/rejected")
    db.commit()
    db.refresh(report)
    notify(
        db, report.reporter_id, "report_feedback", msg,
        summary=report.result or msg, ref_id=report.target_id,
        ref_type={TARGET_POST: "post", TARGET_COMMENT: "comment", TARGET_USER: "user"}.get(report.target_type),
        actor_id=handler.id,
    )
    return report


def _check_target(db: Session, target_type: int, target_id: int) -> None:
    if target_type == TARGET_POST:
        post = db.get(Post, target_id)
        if post is None or post.status != POST_STATUS_NORMAL:
            raise NotFoundError("帖子不存在")
    elif target_type == TARGET_COMMENT:
        comment = db.get(Comment, target_id)
        if comment is None or comment.status not in (0, 2):
            raise NotFoundError("评论不存在")
    elif target_type == TARGET_USER:
        user = db.get(User, target_id)
        if user is None or user.status == 2:
            raise NotFoundError("用户不存在")
    elif target_type == TARGET_COMMUNITY:
        community = db.get(Community, target_id)
        if community is None:
            raise NotFoundError("频道不存在")
    else:
        raise ParamError("举报类型仅支持 1帖子 2评论 3用户 4频道")


def _reports_out(db: Session, rows: list[Report]) -> list[dict]:
    """批量输出增强：一次性预取 reporter/handler，避免每行 N+1 查询。"""
    uids = {r.reporter_id for r in rows} | {r.handler_id for r in rows if r.handler_id}
    users = (
        {u.id: u for u in db.execute(select(User).where(User.id.in_(uids))).scalars()}
        if uids else {}
    )
    items = []
    for r in rows:
        reporter = users.get(r.reporter_id)
        handler = users.get(r.handler_id) if r.handler_id else None
        items.append({
            "id": r.id,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "reason_type": r.reason_type,
            "detail": r.detail,
            "evidence": r.evidence or [],
            "status": r.status,
            "result": r.result,
            "handler_id": r.handler_id,
            "handler_nickname": (handler.nickname or handler.username) if handler else "",
            "handled_at": r.handled_at.strftime("%Y-%m-%d %H:%M:%S") if r.handled_at else None,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
            "reporter_id": r.reporter_id,
            "reporter_nickname": (reporter.nickname or reporter.username) if reporter else "",
        })
    return items
