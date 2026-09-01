"""外链图片代理：QQ 频道 CDN（channelgz.photo.store.qq.com 等）带 Referer 防盗链，
浏览器直接 <img> 引用会 403。此接口由服务端取回图片流式转发（不发 Referer）。

安全约束（与 AI 绘画 draw_api_url 同款 SSRF 防线）：
- 域名白名单：仅放行 QQ 图片 CDN 域，其他一律拒绝
- 白名单域名再做字面量内网/回环拦截（双保险）
- 响应必须 magic bytes 校验为图片，Content-Type 强制按实际类型
- 大小上限（防把代理当无限流量管道）
"""
import ipaddress
from urllib.parse import unquote, urlsplit

import requests
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.response import ParamError

router = APIRouter(prefix="/img_proxy", tags=["img_proxy"])

# 允许代理的图片 CDN 域（QQ 频道图片体系；后续需要可扩充）
ALLOWED_HOSTS: set[str] = {
    "channelgz.photo.store.qq.com",
    "channel.photo.store.qq.com",
}

# 代理上限：QQ 原图一般 < 10MB，给足余量
MAX_PROXY_SIZE = 20 * 1024 * 1024
FETCH_TIMEOUT = (5, 20)  # (连接, 读取)

# 图片类型嗅探：前 16 字节 → MIME（只有识别出图片才放行，防文本/HTML 注入）
_SNIFF: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "image/webp"),  # 第 8 字节处为 WEBP，下方再确认
]


def _is_private_host(host: str) -> bool:
    """字面量内网/回环判定（防白名单域名被 hosts 劫持指到内网；双保险用）。"""
    h = host.strip().strip("[]")
    low = h.lower()
    if low in ("localhost", "0.0.0.0") or low.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast


def _sniff_image(head: bytes) -> str | None:
    """返回识别出的图片 MIME；非图片（或 RIFF 非 WEBP）返回 None。"""
    for magic, mime in _SNIFF:
        if head.startswith(magic):
            if magic == b"RIFF":
                return mime if head[8:12] == b"WEBP" else None
            return mime
    return None


@router.get("")
def proxy_image(url: str):
    """代理转发白名单域名的图片。url 为原始完整 URL（需 URL 编码传入）。"""
    target = unquote(url)
    parsed = urlsplit(target)
    host = (parsed.hostname or "").lower()

    if parsed.scheme not in ("http", "https"):
        raise ParamError("仅支持 http/https 图片链接")
    if host not in ALLOWED_HOSTS:
        raise ParamError("该图片域名不在代理白名单内")
    if _is_private_host(host):
        raise ParamError("图片地址不合法")

    try:
        # stream=True 流式转发，避免大图整载内存；Referer 不发（绕防盗链的关键）
        upstream = requests.get(target, stream=True, timeout=FETCH_TIMEOUT)
    except requests.RequestException:
        raise ParamError("图片源获取失败，请稍后重试")

    with upstream:
        if upstream.status_code != 200:
            raise ParamError(f"图片源返回 {upstream.status_code}（链接可能已过期失效）")

        content_length = upstream.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_PROXY_SIZE:
            raise ParamError("图片超过代理大小限制")

        # 先取首块嗅探类型（防把 HTML 错误页当图片喂给浏览器）
        it = upstream.iter_content(chunk_size=64 * 1024)
        try:
            first = next(it)
        except StopIteration:
            raise ParamError("图片源返回空内容")
        mime = _sniff_image(first[:16])
        if not mime:
            raise ParamError("代理目标不是有效图片")

        def gen():
            yield first
            sent = len(first)
            for chunk in it:
                sent += len(chunk)
                if sent > MAX_PROXY_SIZE:
                    break  # 超限即断流（Content-Length 已预检，此处防声明造假）
                yield chunk

        # 缓存策略：URL 带签名参数本身即随内容唯一，代理可长缓存
        return StreamingResponse(
            gen(),
            media_type=mime,
            headers={"Cache-Control": "public, max-age=86400"},
        )
