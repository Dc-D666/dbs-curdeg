"""运营管理接口（阶段 7）：数据看板 / 审核记录管理 / 用户封禁 / 敏感词库（系统管理员 user_type=1）。"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import PermissionError_, ok
from app.db import get_db
from app.models.user import User
from app.services import admin_service, ai_call_log_service, ai_config_service, sensitive_word_service, stats_service, system_config_service

router = APIRouter(prefix="/admin", tags=["admin"])
public_router = APIRouter(tags=["admin"])  # 公开配置，不挂 /admin 前缀


def require_admin(user: User = Depends(get_current_user)) -> User:
    """系统管理员（user_type=1）才能访问运营接口。"""
    if user.user_type != 1:
        raise PermissionError_("需要系统管理员权限")
    return user


class HandleReviewRequest(BaseModel):
    approve: bool


class UserStatusRequest(BaseModel):
    status: int  # 0正常 1封禁 2注销


class SensitiveWordRequest(BaseModel):
    word: str = Field(min_length=1, max_length=64)
    category: str = Field(default="其他", max_length=32)


class AnnouncementRequest(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    content: str = Field(default="", max_length=500)


@router.post("/announcement")
def admin_broadcast_announcement(
    payload: AnnouncementRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """发布更新公告：向全部正常用户发送系统通知。"""
    n = admin_service.broadcast_announcement(db, admin, payload.title, payload.content)
    return ok(data={"recipients": n}, message="公告已发布")


@router.get("/stats")
def admin_stats(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """运营看板：全局用户/频道/内容/互动统计 + 近 7 天发帖趋势 + Top 频道。"""
    return ok(data=admin_service.overview_stats(db))


@router.put("/users/{user_id}/status")
def admin_user_status(
    user_id: int,
    payload: UserStatusRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """封禁/解封/注销用户（系统管理员）。"""
    user = admin_service.set_user_status(db, user_id, payload.status)
    return ok(data={"id": user.id, "status": user.status}, message="账号状态已更新")


@router.get("/communities")
def admin_communities(
    keyword: str | None = Query(None, max_length=64),
    status: int | None = Query(None, ge=0, le=2),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """平台级频道列表：全部频道（含封禁/关闭）+ 成员/帖数 + 归属者，供巡视与封禁解封。"""
    return ok(data=admin_service.list_communities(db, keyword, status, page, page_size))


@router.get("/users")
def admin_users(
    keyword: str | None = Query(None, max_length=64),
    status: int | None = Query(None, ge=0, le=2),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """平台级用户列表：全部用户（含封禁/注销）+ 账号状态 + 加入频道数，供封禁/解封。"""
    return ok(data=admin_service.list_users(db, keyword, status, page, page_size))


@router.get("/reviews")
def admin_reviews(
    status: int | None = Query(None, ge=0, le=3),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """审核记录列表（可按状态过滤：0待审 1通过 2驳回 3转人工）。"""
    return ok(data=admin_service.list_reviews(db, status, page, page_size))


@router.post("/reviews/{review_id}/handle")
def admin_handle_review(
    review_id: int,
    payload: HandleReviewRequest,
    reviewer: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """人工处理转人工复审的记录（通过恢复帖子 / 维持驳回），并通知作者。"""
    admin_service.handle_review(db, reviewer, review_id, payload.approve)
    return ok(message="已处理" if payload.approve else "已驳回")


# ---------- 敏感词库（文档⑪） ----------


@router.get("/sensitive-words")
def admin_sensitive_words(
    category: str | None = Query(None, max_length=32),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """敏感词列表（可按分类过滤）。"""
    return ok(data=sensitive_word_service.list_words(db, page, page_size, category))


@router.post("/sensitive-words")
def admin_add_sensitive_word(
    payload: SensitiveWordRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """新增敏感词。"""
    sw = sensitive_word_service.add_word(db, payload.word, payload.category)
    return ok(data={"id": sw.id, "word": sw.word, "category": sw.category}, message="已添加")


@router.put("/sensitive-words/{word_id}/enabled")
def admin_set_sensitive_word_enabled(
    word_id: int,
    enabled: bool = Query(True),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """启用/停用敏感词。"""
    sensitive_word_service.set_word_enabled(db, word_id, enabled)
    return ok(message="已启用" if enabled else "已停用")


@router.delete("/sensitive-words/{word_id}")
def admin_delete_sensitive_word(
    word_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除敏感词。"""
    sensitive_word_service.delete_word(db, word_id)
    return ok(message="已删除")


# ---------- 系统基础配置（文档⑳） ----------


class ConfigRequest(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    value: str = ""
    description: str = Field(default="", max_length=255)


@router.get("/configs")
def admin_configs(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """全部系统配置（管理端）。"""
    return ok(data=system_config_service.list_all(db))


@router.put("/configs")
def admin_set_config(
    payload: ConfigRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """设置/更新系统配置（upsert）。"""
    conf = system_config_service.set_config(db, payload.key, payload.value, payload.description)
    return ok(data={"key": conf.key, "value": conf.value}, message="配置已保存")


@public_router.get("/public/config")
def public_config(db: Session = Depends(get_db)):
    """公开配置：站点名称/备案/版权（游客可读）。"""
    return ok(data=system_config_service.public_configs(db))


# ---------- AI 调用日志（文档⑰） ----------


@router.get("/ai-logs")
def admin_ai_logs(
    feature: str | None = Query(None, max_length=32),
    status: str | None = Query(None, max_length=16),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """AI 调用日志查询（可按功能/状态过滤）。"""
    return ok(data=ai_call_log_service.query_logs(db, feature, status, page, page_size))


@router.get("/ai-logs/summary")
def admin_ai_logs_summary(
    days: int = Query(7, ge=1, le=90),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """AI 调用汇总（近 N 天按功能统计）。"""
    return ok(data=ai_call_log_service.summary(db, days))


# ---------- 数据看板与报表（文档⑲） ----------


@router.get("/dashboard/trend")
def admin_dashboard_trend(
    days: int = Query(7, ge=1, le=90),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """近 N 天运营趋势（新增/活跃/发帖/互动/违规/AI 调用/留存率）。"""
    return ok(data=stats_service.dashboard_trend(db, days))


@router.get("/dashboard/export")
def admin_dashboard_export(
    days: int = Query(7, ge=1, le=90),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """导出运营统计报表 CSV。"""
    csv_text = stats_service.export_stats(db, days)
    return PlainTextResponse(
        "\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="stats_report.csv"'},
    )


# ---------- AI 功能配置（文档⑰） ----------


class AiConfigRequest(BaseModel):
    enabled: bool | None = None
    model: str | None = Field(default=None, max_length=64)
    params: dict | None = None
    prompt_template: str | None = None
    rate_limit: int | None = Field(default=None, ge=0)


@router.get("/ai-configs")
def admin_ai_configs(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """全部 AI 功能配置。"""
    return ok(data=ai_config_service.list_configs(db))


@router.put("/ai-configs/{feature}")
def admin_update_ai_config(
    feature: str,
    payload: AiConfigRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新 AI 功能配置（开关/模型/参数/prompt/限流）。"""
    conf = ai_config_service.update_config(
        db, feature,
        enabled=payload.enabled,
        model=payload.model,
        params=payload.params,
        prompt_template=payload.prompt_template,
        rate_limit=payload.rate_limit,
    )
    return ok(data={"feature": conf.feature, "enabled": conf.enabled}, message="配置已保存")
