"""统一 LLM 网关（阶段 6，方案 D5）：openai SDK 兼容客户端，智谱主 + DeepSeek 兜底。

- chat(messages) → 文本（主模型异常自动切 DeepSeek）
- stream(messages) → 文本块迭代器（SSE 帮写用）
- embed(text) → 向量（GLM Embedding-3 API；DeepSeek 无 embedding 端点，不做兜底）

测试：直接 monkeypatch 本模块的 chat / stream / embed 三个函数（conftest 已全局 mock）。
"""
import logging

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


def _zhipu() -> OpenAI:
    return OpenAI(api_key=settings.ZHIPU_API_KEY, base_url=settings.ZHIPU_BASE_URL)


def _deepseek() -> OpenAI:
    return OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)


def chat(
    messages: list[dict],
    model: str = "",
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> str:
    """单轮补全（智谱主 → DeepSeek 兜底）。"""
    m = model or settings.ZHIPU_MODEL
    try:
        resp = _zhipu().chat.completions.create(
            model=m, messages=messages, max_tokens=max_tokens, temperature=temperature
        )
        return resp.choices[0].message.content or ""
    except Exception as e:  # 主模型异常：切兜底
        logger.warning("GLM 调用失败(%s)，切换 DeepSeek 兜底", e)
        resp = _deepseek().chat.completions.create(
            model=settings.DEEPSEEK_MODEL, messages=messages,
            max_tokens=max_tokens, temperature=temperature,
        )
        return resp.choices[0].message.content or ""


def stream(
    messages: list[dict],
    model: str = "",
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> iter:
    """流式补全（SSE 用），返回文本块迭代器（主备自动切换）。"""
    m = model or settings.ZHIPU_MODEL
    try:
        resp = _zhipu().chat.completions.create(
            model=m, messages=messages, max_tokens=max_tokens,
            temperature=temperature, stream=True,
        )
        return _iter_text(resp)
    except Exception as e:
        logger.warning("GLM 流式调用失败(%s)，切换 DeepSeek 兜底", e)
        resp = _deepseek().chat.completions.create(
            model=settings.DEEPSEEK_MODEL, messages=messages,
            max_tokens=max_tokens, temperature=temperature, stream=True,
        )
        return _iter_text(resp)


def _iter_text(resp) -> iter:
    for chunk in resp:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def embed(text: str) -> list[float]:
    """文本向量（GLM Embedding-3）。"""
    resp = _zhipu().embeddings.create(model=settings.ZHIPU_EMBED_MODEL, input=text)
    return resp.data[0].embedding
