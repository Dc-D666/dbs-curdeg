"""统一 LLM 网关（阶段 6，方案 D5）：openai SDK 兼容客户端，智谱主 + DeepSeek 兜底。

- chat(messages) → 文本（主模型异常自动切 DeepSeek）
- stream(messages) → 文本块迭代器（SSE 帮写用）
- embed(text) → 向量（GLM Embedding-3 API；DeepSeek 无 embedding 端点，不做兜底）

测试：直接 monkeypatch 本模块的 chat / stream / embed 三个函数（conftest 已全局 mock）。
"""
import logging

from openai import OpenAI, Timeout

from app.core.config import settings

logger = logging.getLogger(__name__)


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
        return _deepseek_chat(messages, max_tokens, temperature)


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


def embed(text: str) -> list[float]:
    """文本向量（GLM Embedding-3）。"""
    resp = _zhipu().embeddings.create(model=settings.ZHIPU_EMBED_MODEL, input=text)
    return resp.data[0].embedding
