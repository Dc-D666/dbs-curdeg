"""AI 帮写（阶段 6，POST /ai/assist SSE 流式）：按频道风格生成/润色/起标题。"""
import asyncio

from fastapi import Request

from app.ai import llm_gateway

SYSTEM_PROMPT = (
    "你是「频道社区」的资深发帖助手，擅长根据用户要求撰写或润色帖子内容。"
    "要求：内容口语化、有网感但不低俗；结构清晰（可分段、用 emoji 点缀）；"
    "不要输出 Markdown 标题语法（#）；直接输出正文，不要任何解释性前缀。"
)

ACTION_HINTS = {
    "write": "请根据以下主题/标题写一篇帖子正文（200 字左右）：\n",
    "polish": "请润色以下帖子内容，使其更通顺、更有吸引力（保持原意，可适当扩写）：\n",
    "title": "请为以下内容起 3 个简洁有吸引力的标题（每个一行，不要编号）：\n",
}


def build_messages(payload) -> list[dict]:
    """组装 prompt：system + 动作提示 + 已有内容。"""
    action = payload.action if payload.action in ACTION_HINTS else "write"
    content = payload.content or ""
    title = payload.title or ""
    user = ACTION_HINTS[action]
    if title:
        user += f"标题：{title}\n"
    if content:
        user += f"内容：{content}\n"
    user += "（若提供的信息不足，可以基于常见场景合理补充。）"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


async def assist_stream(payload, request: Request) -> iter:
    """SSE 文本块迭代器（异步生成器，支持客户端断开检查）。

    说明：GLM-4.7-Flash 是推理模型，流式响应 content 恒为空（思考过程在
    reasoning_content），因此这里用 chat 一次性取回完整文本，再按小块切分
    模拟流式（前端打字机效果不变，SSE 协议不变）。

    生成期间定期检查客户端是否断开，断开则提前终止，避免无效占用的 LLM 与
    线程继续运行。
    """
    msgs = build_messages(payload)
    text = await asyncio.to_thread(llm_gateway.chat, msgs, "", 2048, 0.7)
    step = 8
    for i in range(0, len(text), step):
        if await request.is_disconnected():
            return
        yield text[i:i + step]
