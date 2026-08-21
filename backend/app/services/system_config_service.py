"""系统基础配置服务（文档⑳系统基础配置管理，P0）。

键值对存运行时配置：站点名称、备案信息、上传大小限制、允许文件格式、
全局敏感词开关等。public_keys 为可公开读取的键（站点名/备案等）。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.response import ParamError
from app.models.system_config import SystemConfig

# 可公开读取的配置键（首页/页脚展示用）
PUBLIC_KEYS = ("site_name", "site_icp", "site_copyright")

DEFAULTS: dict[str, dict] = {
    "site_name": {"value": "SDUdiscord", "description": "站点名称"},
    "site_icp": {"value": "", "description": "备案信息"},
    "site_copyright": {"value": "", "description": "版权信息"},
    "upload_max_size": {"value": "5242880", "description": "上传大小限制（字节）"},
    "upload_allowed_ext": {"value": "jpg,jpeg,png,webp,gif,mp4,mov,pdf,zip,doc,docx,xls,xlsx,txt,md", "description": "允许上传文件格式"},
    "sensitive_switch": {"value": "1", "description": "全局敏感词开关（1开 0关）"},
    "default_user_perms": {"value": "", "description": "默认用户权限（预留）"},
}


def get(db: Session, key: str) -> str | None:
    row = db.execute(select(SystemConfig.value).where(SystemConfig.key == key)).scalar_one_or_none()
    if row is not None:
        return str(row)
    default = DEFAULTS.get(key)
    return default["value"] if default else None


def set_config(db: Session, key: str, value: str, description: str = "") -> SystemConfig:
    """设置配置（upsert）。"""
    if not key or len(key) > 64:
        raise ParamError("配置键不能为空且不超过 64 字符")
    existing = db.execute(select(SystemConfig).where(SystemConfig.key == key)).scalar_one_or_none()
    if existing:
        existing.value = str(value)
        if description:
            existing.description = description
        db.commit()
        db.refresh(existing)
        return existing
    conf = SystemConfig(key=key, value=str(value), description=description)
    db.add(conf)
    db.commit()
    db.refresh(conf)
    return conf


def list_all(db: Session) -> list[dict]:
    """全部配置（管理端）。"""
    rows = db.execute(select(SystemConfig).order_by(SystemConfig.key)).scalars().all()
    return [{"key": r.key, "value": r.value, "description": r.description} for r in rows]


def public_configs(db: Session) -> dict:
    """公开配置（站点名/备案/版权）。"""
    result = {}
    for key in PUBLIC_KEYS:
        result[key] = get(db, key) or DEFAULTS[key]["value"]
    return result
