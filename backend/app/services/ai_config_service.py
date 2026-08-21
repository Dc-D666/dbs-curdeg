"""AI 功能配置服务（文档⑰AI 能力配置管理，P0）。

feature：assist(帮写) / review(审核) / rag(问答) / summary(摘要) / draw(绘画)。
管理端可开关功能、切换模型、编辑 prompt 模板。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.response import NotFoundError, ParamError
from app.models.ai_config import AiConfig

FEATURES = ("assist", "review", "rag", "summary", "draw")

DEFAULTS: dict[str, dict] = {
    "assist": {"model": "", "prompt": ""},
    "review": {"model": "", "prompt": ""},
    "rag": {"model": "", "prompt": ""},
    "summary": {"model": "", "prompt": ""},
    "draw": {"model": "", "prompt": ""},
}


def list_configs(db: Session) -> list[dict]:
    """全部 AI 功能配置（含默认值兜底）。"""
    rows = db.execute(select(AiConfig)).scalars().all()
    by_feature = {r.feature: r for r in rows}
    result = []
    for feature in FEATURES:
        r = by_feature.get(feature)
        if r is None:
            result.append({
                "feature": feature,
                "enabled": True,
                "model": DEFAULTS[feature]["model"],
                "params": {},
                "prompt_template": DEFAULTS[feature]["prompt"],
                "rate_limit": 0,
            })
        else:
            result.append({
                "feature": r.feature,
                "enabled": r.enabled,
                "model": r.model,
                "params": r.params or {},
                "prompt_template": r.prompt_template,
                "rate_limit": r.rate_limit,
            })
    return result


def get_config(db: Session, feature: str) -> AiConfig | None:
    return db.execute(select(AiConfig).where(AiConfig.feature == feature)).scalar_one_or_none()


def update_config(
    db: Session, feature: str, *, enabled: bool | None = None, model: str | None = None,
    params: dict | None = None, prompt_template: str | None = None, rate_limit: int | None = None,
) -> AiConfig:
    """更新 AI 功能配置（upsert，仅更新提供的字段）。"""
    if feature not in FEATURES:
        raise ParamError(f"feature 仅支持 {'/'.join(FEATURES)}")
    conf = get_config(db, feature)
    if conf is None:
        conf = AiConfig(feature=feature)
        db.add(conf)
    if enabled is not None:
        conf.enabled = enabled
    if model is not None:
        conf.model = model[:64]
    if params is not None:
        conf.params = params
    if prompt_template is not None:
        conf.prompt_template = prompt_template
    if rate_limit is not None:
        conf.rate_limit = rate_limit
    db.commit()
    db.refresh(conf)
    return conf
