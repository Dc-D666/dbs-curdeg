"""统一 LLM 网关（阶段 6，方案 D5）：openai SDK 兼容客户端，智谱主 + DeepSeek 兜底。

- chat(messages) → 文本（主模型异常自动切 DeepSeek）
- stream(messages) → 文本块迭代器（SSE 帮写用）
- embed(text) → 向量（GLM Embedding-3 API；DeepSeek 无 embedding 端点，不做兜底）

调用自动写 ai_call_logs（P0 文档⑰），写日志失败静默不影响主流程。
feature 参数供调用方标注业务功能（assist/review/rag/summary）。

测试：直接 monkeypatch 本模块的 chat / stream / embed 三个函数（conftest 已全局 mock）。
"""
import logging
import time

from openai import OpenAI, Timeout
from sqlalchemy import select

from app.core.config import settings
from app.core.response import FeatureDisabledError
from app.services.ai_call_log_service import log_ai_call

logger = logging.getLogger(__name__)

# 管理端 AI 开关缓存（ai_configs.enabled）：60s 进程内缓存，空表/无记录 = 默认开启
_FEATURE_TTL = 60
_feature_cache: dict[str, tuple[bool, float]] = {}


def _ensure_feature_enabled(feature: str) -> None:
    """消费 ai_configs.enabled（08-29 整改：此前管理端改配置不生效）。

    - 无记录 → 默认开启（兼容历史行为，测试库空表不受影响）
    - enabled=0 → 抛 FeatureDisabledError（403 友好提示）
    - 读配置失败不阻断主流程
    """
    now = time.monotonic()
    cached = _feature_cache.get(feature)
    if cached and now - cached[1] < _FEATURE_TTL:
        if not cached[0]:
            raise FeatureDisabledError()
        return
    enabled = True
    try:
        from app.db import SessionLocal
        from app.models.ai_config import AiConfig

        db = SessionLocal()
        try:
            row = db.execute(
                select(AiConfig.enabled).where(AiConfig.feature == feature)
            ).scalar_one_or_none()
        finally:
            db.close()
        if row is not None:
            enabled = bool(row)
    except Exception:
        logger.exception("ai_configs 开关读取失败 feature=%s，按开启处理", feature)
    _feature_cache[feature] = (enabled, now)
    if not enabled:
        raise FeatureDisabledError()


def _zhipu() -> OpenAI:
    return OpenAI(
        api_key=settings.ZHIPU_API_KEY,
        base_url=settings.ZHIPU_BASE_URL,
        timeout=Timeout(connect=5, read=30, write=30, pool=5),
    )


def _deepseek() -> OpenAI:
    return OpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        timeout=Timeout(connect=5, read=30, write=30, pool=5),
    )


def chat(
    messages: list[dict],
    model: str = "",
    max_tokens: int = 1024,
    temperature: float = 0.7,
    feature: str = "chat",
    user_id: int | None = None,
) -> str:
    """单轮补全（智谱主 → DeepSeek 兜底），自动记录调用日志。

    优化 08-29：回填 response.usage 的 token 计量；主模型失败后兜底成功
    记 status='degraded'（区分"最终成功"与"发生过降级/限流"）。
    """
    m = model or settings.ZHIPU_MODEL
    start = time.monotonic()
    _ensure_feature_enabled(feature)
    try:
        resp = _zhipu().chat.completions.create(
            model=m, messages=messages, max_tokens=max_tokens, temperature=temperature
        )
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        log_ai_call(
            feature, user_id, m, int((time.monotonic() - start) * 1000), "ok",
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )
        return text
    except Exception as e:  # 主模型异常：切兜底
        logger.warning("GLM 调用失败(%s)，切换 DeepSeek 兜底", e)
        text = _deepseek_chat(messages, max_tokens, temperature)
        log_ai_call(
            feature, user_id, settings.DEEPSEEK_MODEL,
            int((time.monotonic() - start) * 1000),
            "degraded" if text else "error", str(e)[:512],
        )
        return text


def stream(
    messages: list[dict],
    model: str = "",
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> iter:
    """流式补全（SSE 用），返回文本块迭代器（主备自动切换）。

    主模型 .create() 建立流或流式迭代任一环节异常，都会回退 DeepSeek：
    迭代异常时一次性取回完整文本再分块模拟流式，确保主备切换覆盖整个
    流式生成过程。
    """
    m = model or settings.ZHIPU_MODEL
    _ensure_feature_enabled(feature)
    try:
        resp = _zhipu().chat.completions.create(
            model=m, messages=messages, max_tokens=max_tokens,
            temperature=temperature, stream=True,
        )
    except Exception as e:
        logger.warning("GLM 流式调用失败(%s)，切换 DeepSeek 兜底", e)
        yield from _deepseek_stream(messages, max_tokens, temperature)
        return
    try:
        yield from _iter_text(resp)
    except Exception as e:
        logger.warning("GLM 流式迭代失败(%s)，切换 DeepSeek 兜底", e)
        yield from _deepseek_stream(messages, max_tokens, temperature)


def _deepseek_chat(messages: list[dict], max_tokens: int, temperature: float) -> str:
    """DeepSeek 一次取回完整文本（兜底）。"""
    try:
        resp = _deepseek().chat.completions.create(
            model=settings.DEEPSEEK_MODEL, messages=messages,
            max_tokens=max_tokens, temperature=temperature,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.error("DeepSeek 兜底也失败(%s)", e)
        return ""


def _deepseek_stream(messages: list[dict], max_tokens: int, temperature: float) -> iter:
    """DeepSeek 兜底流式：完整取回后分块模拟流式（保持 SSE 协议/打字机效果）。"""
    text = _deepseek_chat(messages, max_tokens, temperature)
    step = 16
    for i in range(0, len(text), step):
        yield text[i:i + step]


def _iter_text(resp) -> iter:
    for chunk in resp:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def embed(text: str, feature: str = "embed", user_id: int | None = None) -> list[float]:
    """文本向量（GLM Embedding-3），自动记录调用日志。"""
    start = time.monotonic()
    _ensure_feature_enabled(feature)
    try:
        resp = _zhipu().embeddings.create(model=settings.ZHIPU_EMBED_MODEL, input=text)
        result = resp.data[0].embedding
        usage = getattr(resp, "usage", None)
        log_ai_call(
            feature, user_id, settings.ZHIPU_EMBED_MODEL, int((time.monotonic() - start) * 1000),
            "ok", prompt_tokens=getattr(usage, "total_tokens", 0) or 0,
        )
        return result
    except Exception as e:
        log_ai_call(
            feature, user_id, settings.ZHIPU_EMBED_MODEL,
            int((time.monotonic() - start) * 1000), "error", str(e)[:512],
        )
        raise
