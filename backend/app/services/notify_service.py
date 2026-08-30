"""通知业务逻辑（阶段 5）：落库 + WS 推送 + 开关过滤。

流程：触发点（评论/点赞/关注/@/审核/管理动作）在事务提交后调用 notify()：
  1. 校验接收者存在且对应通知开关开启（users.notify_settings JSON，键见 SETTINGS_KEYS）；
  2. 自己触发自己的动作不通知；
  3. 插入 notifications 行并提交；
  4. 经 ws/events.push_event 异步推送（在线才推，离线不补推——列表里有）。
"""
import logging

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.response import NotFoundError, ParamError
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationOut, NotifySettingsUpdate
from app.ws import events

logger = logging.getLogger(__name__)

# 通知开关键（文档⑬：mention/like/comment/follow/system/review/report）
SETTINGS_KEYS = ("mention", "like", "comment", "follow", "system", "review", "report")

# notifications.type → 通知开关键（review_result 归 review 管，report_feedback 归 report）
_TYPE_TO_SETTING = {
    events.EVENT_MENTION: "mention",
    events.EVENT_LIKE: "like",
    events.EVENT_COMMENT: "comment",
    events.EVENT_FOLLOW: "follow",
    events.EVENT_SYSTEM: "system",
    events.EVENT_REVIEW_RESULT: "review",
    events.EVENT_REPORT_FEEDBACK: "report",
}

DEFAULT_SETTINGS = {k: True for k in SETTINGS_KEYS}


# ---------- 开关 ----------


def get_settings(db: Session, user: User) -> dict:
    """当前通知开关（未设置的键默认开）。"""
    settings = user.notify_settings or {}
    return {k: bool(settings.get(k, True)) for k in SETTINGS_KEYS}


def update_settings(db: Session, user: User, patch: dict) -> dict:
    """更新通知开关（部分更新，合并保留其他键）。"""
    unknown = set(patch) - set(SETTINGS_KEYS)
    if unknown:
        raise ParamError(f"未知通知开关: {sorted(unknown)}")
    current = get_settings(db, user)
    current.update({k: bool(v) for k, v in patch.items()})
    user.notify_settings = current
    db.commit()
    return current


# ---------- 通知生成 ----------


def notify(
    db: Session,
    user_id: int,
    ntype: str,
    title: str,
    summary: str = "",
    ref_id: int | None = None,
    ref_type: str | None = None,
    actor_id: int | None = None,
    community_id: int | None = None,
) -> Notification | None:
    """创建一条通知并推送（接收者开关关闭 / 自己触发自己 / 接收者不存在时跳过）。

    注意：本函数会提交当前 session 事务（内部执行 db.commit() + db.refresh()），
    因为多个调用方在 notify() 之后不再单独 commit（get_db 请求级会话也不自动提交），
    而通知行依赖此处 commit 才得以持久化。请勿在调用方事务中途依赖本函数的分支提交。
    """
    if actor_id == user_id:
        return None
    user = db.get(User, user_id)
    if user is None or user.status != 0:
        return None
    settings = user.notify_settings or {}
    setting_key = _TYPE_TO_SETTING.get(ntype, "system")
    if not bool(settings.get(setting_key, True)):
        return None

    n = Notification(
        user_id=user_id,
        type=ntype,
        title=title[:128],
        summary=summary[:255],
        ref_id=ref_id,
        ref_type=ref_type,
        actor_id=actor_id,
        community_id=community_id,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    try:
        events.push_event(user_id, events.EVENT_NOTIFICATION, events.notification_payload(n))
    except Exception:  # pragma: no cover - 推送失败不影响业务
        logger.exception("WebSocket 推送失败 user_id=%s", user_id)
    return n


# ---------- 查询 / 已读 ----------


def list_notifications(
    db: Session, user_id: int, page: int, page_size: int
) -> dict:
    """通知分页：未读在前，按时间倒序。"""
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.is_read.asc(), Notification.id.desc())
    )
    total = db.execute(
        select(func.count(Notification.id)).where(Notification.user_id == user_id)
    ).scalar_one()
    items = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return {
        "items": _decorate(db, items),
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def unread_count(db: Session, user_id: int) -> int:
    """未读通知数（前端角标用）。"""
    return db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id, Notification.is_read.is_(False)
        )
    ).scalar_one()


def mark_read(db: Session, user_id: int, notification_id: int) -> None:
    """单条已读（只能读自己的）。"""
    n = db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    ).scalar_one_or_none()
    if n is None:
        raise NotFoundError("通知不存在")
    if not n.is_read:
        n.is_read = True
        n.read_at = func.now()
        db.commit()


def mark_all_read(db: Session, user_id: int) -> int:
    """全部已读，返回本次标记条数。"""
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=func.now())
    )
    db.commit()
    return result.rowcount or 0


def delete_notification(db: Session, user_id: int, notification_id: int) -> None:
    """删除一条通知（只能删自己的）。"""
    n = db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    ).scalar_one_or_none()
    if n is None:
        raise NotFoundError("通知不存在")
    db.delete(n)
    db.commit()


# ---------- 内部 ----------


def _decorate(db: Session, items: list[Notification]) -> list[NotificationOut]:
    """批量输出增强：一次性取 actor/community 映射，避免 N+1 查询。"""
    actor_ids = {n.actor_id for n in items if n.actor_id}
    community_ids = {n.community_id for n in items if n.community_id}

    from app.models.user import User as U

    actors: dict[int, U] = {}
    if actor_ids:
        actors = {
            u.id: u
            for u in db.execute(select(U).where(U.id.in_(actor_ids))).scalars()
        }

    from app.models.community import Community

    communities: dict[int, Community] = {}
    if community_ids:
        communities = {
            c.id: c
            for c in db.execute(
                select(Community).where(Community.id.in_(community_ids))
            ).scalars()
        }

    results: list[NotificationOut] = []
    for n in items:
        out = NotificationOut.model_validate(n)
        actor = actors.get(n.actor_id) if n.actor_id else None
        if actor:
            out.actor_nickname = actor.nickname or actor.username
            out.actor_avatar = actor.avatar_url
        c = communities.get(n.community_id) if n.community_id else None
        if c:
            out.community_name = c.name
        results.append(out)
    return results
