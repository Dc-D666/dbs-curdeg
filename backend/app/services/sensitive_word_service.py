"""敏感词库服务（文档⑪敏感词库维护/即时拦截，P0）。

- 发帖/评论前调用 contains_sensitive(text) 即时拦截（命中即拒绝，不进入 AI 队列）
- 词库加载带进程内缓存（TTL 60s），管理员增删后由 load_words(refresh=True) 主动刷新
- 全局开关 system_config.sensitive_switch（默认开）
"""
import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.response import NotFoundError, ParamError
from app.models.sensitive_word import SensitiveWord
from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)

_CACHE: dict = {"ts": 0.0, "words": []}
CACHE_TTL = 60


def load_words(db: Session, refresh: bool = False) -> list[str]:
    """加载启用中的敏感词（进程内缓存 TTL 60s；增删后传 refresh=True 立即刷新）。"""
    now = time.time()
    if refresh or now - _CACHE["ts"] > CACHE_TTL:
        words = db.execute(
            select(SensitiveWord.word).where(SensitiveWord.enabled.is_(True))
        ).scalars().all()
        _CACHE.update({"ts": now, "words": list(words)})
    return _CACHE["words"]


def check_text(db: Session, text: str) -> list[str]:
    """返回命中的敏感词列表（空 = 干净）。"""
    if not text:
        return []
    words = load_words(db)
    if not words:
        return []
    return [w for w in words if w and w in text]


def contains_sensitive(db: Session, text: str) -> bool:
    """是否含敏感词（拦截判定用）。"""
    return bool(check_text(db, text))


def ensure_switch_on(db: Session) -> bool:
    """全局敏感词开关（system_config.sensitive_switch，默认开）。"""
    row = db.execute(
        select(SystemConfig.value).where(SystemConfig.key == "sensitive_switch")
    ).scalar_one_or_none()
    if row is None:
        return True
    return str(row).strip().lower() not in ("0", "false", "off")


def add_word(db: Session, word: str, category: str = "其他") -> SensitiveWord:
    """新增敏感词（去重 upsert）。"""
    word = word.strip()
    if not word:
        raise ParamError("敏感词不能为空")
    if len(word) > 64:
        raise ParamError("敏感词过长")
    existing = db.execute(
        select(SensitiveWord).where(SensitiveWord.word == word)
    ).scalar_one_or_none()
    if existing:
        existing.category = category[:32] or existing.category
        existing.enabled = True
        db.commit()
        db.refresh(existing)
        load_words(db, refresh=True)
        return existing
    sw = SensitiveWord(word=word, category=category[:32])
    db.add(sw)
    db.commit()
    db.refresh(sw)
    load_words(db, refresh=True)
    return sw


def list_words(db: Session, page: int, page_size: int, category: str | None = None) -> dict:
    """敏感词列表（分页，可过滤分类）。"""
    stmt = select(SensitiveWord).order_by(SensitiveWord.id.desc())
    if category:
        stmt = stmt.where(SensitiveWord.category == category)
    count_stmt = select(func.count(SensitiveWord.id))
    if category:
        count_stmt = count_stmt.where(SensitiveWord.category == category)
    total = db.execute(count_stmt).scalar_one()
    items = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return {
        "items": [
            {"id": w.id, "word": w.word, "category": w.category, "enabled": w.enabled}
            for w in items
        ],
        "total": total, "page": page, "page_size": page_size,
    }


def set_word_enabled(db: Session, word_id: int, enabled: bool) -> None:
    """启用/停用敏感词。"""
    sw = db.get(SensitiveWord, word_id)
    if sw is None:
        raise NotFoundError("敏感词不存在")
    sw.enabled = enabled
    db.commit()
    load_words(db, refresh=True)


def delete_word(db: Session, word_id: int) -> None:
    """删除敏感词。"""
    sw = db.get(SensitiveWord, word_id)
    if sw is None:
        raise NotFoundError("敏感词不存在")
    db.delete(sw)
    db.commit()
    load_words(db, refresh=True)
