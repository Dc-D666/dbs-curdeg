"""上传服务：图片保存到共享卷 /app/uploads，nginx 直服 /uploads/。"""
import uuid
from datetime import date
from pathlib import Path

from fastapi import UploadFile

from app.core.response import ParamError

UPLOAD_ROOT = Path("/app/uploads")
ALLOWED_EXT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
# 附件（文档⑦：图片/视频/文件）；视频/文件走独立类型，避开图片校验
ALLOWED_ATTACH_EXT = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".gif": "image/gif",
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
    ".pdf": "application/pdf", ".zip": "application/zip",
    ".doc": "application/msword", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain", ".md": "text/markdown",
}
MAX_SIZE = 5 * 1024 * 1024  # 5MB（可被 system_config.upload_max_size 覆盖，见 configured_max_size）


def configured_max_size(db) -> int:
    """上传大小上限（字节）：读 system_config.upload_max_size（MB），缺省 5MB。"""
    from app.services.system_config_service import get

    mb_str = get(db, "upload_max_size")
    try:
        mb = int(mb_str) if mb_str else 5
        return max(1, mb) * 1024 * 1024
    except (TypeError, ValueError):
        return MAX_SIZE

# 扩展名 → 期望的文件头（magic bytes，防"图片后缀+恶意内容"伪装）。txt/md 无固定头不校验。
_MAGIC: dict[str, tuple[bytes, ...]] = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".webp": (b"RIFF",),  # 前 4 字节 RIFF，offset 8 处为 WEBP
    ".mp4": (b"\x00\x00\x00",),
    ".mov": (b"\x00\x00\x00",),
    ".webm": (b"\x1a\x45\xdf\xa3",),
    ".pdf": (b"%PDF-",),
    ".zip": (b"PK\x03\x04",),
    ".docx": (b"PK\x03\x04",),  # docx/xlsx 本质是 zip
    ".xlsx": (b"PK\x03\x04",),
    ".doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),  # OLE
    ".xls": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
}


def _assert_magic(content: bytes, ext: str) -> None:
    """校验文件头与扩展名匹配；无固定头类型（txt/md）跳过。"""
    if not content:
        raise ParamError("上传文件为空")
    if ext not in _MAGIC:
        return
    # 部分格式在固定 offset 才出现关键标识：mp4/mov 的第 4 字节起为 ftyp；webp 第 8 字节起为 WEBP
    window = content[:16]
    if ext in (".mp4", ".mov"):
        if b"ftyp" not in window[4:12] and not (ext == ".mov" and b"moov" in window[4:12]):
            raise ParamError("文件内容与扩展名不匹配")
        return
    if ext == ".webp":
        if window[:4] != b"RIFF" or window[8:12] != b"WEBP":
            raise ParamError("文件内容与扩展名不匹配")
        return
    if not any(window.startswith(m) for m in _MAGIC[ext]):
        raise ParamError("文件内容与扩展名不匹配")


def _read_body(file: UploadFile, limit: int) -> bytes:
    content = file.file.read()
    if len(content) > limit:
        raise ParamError(f"文件大小不能超过 {format(limit / (1024 * 1024), 'g')}MB")
    return content


def save_image(file: UploadFile, max_size: int = MAX_SIZE) -> str:
    """保存图片，返回 URL 路径（如 /uploads/2026-08-19/xxxx.png）。"""
    if file.size and file.size > max_size:
        raise ParamError("图片大小不能超过 5MB")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ParamError("仅支持 jpg/png/webp/gif 图片")

    # 目录按日期分片
    day_dir = UPLOAD_ROOT / date.today().isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)

    name = f"{uuid.uuid4().hex}{ext}"
    dest = day_dir / name

    content = _read_body(file, max_size)
    _assert_magic(content, ext)
    dest.write_bytes(content)

    return f"/uploads/{date.today().isoformat()}/{name}"


def save_attachment(file: UploadFile, max_size: int = MAX_SIZE) -> dict:
    """保存附件（图片/视频/文件），返回 {url, media_type, file_size}。

    media_type 沿用文档⑦：1图片 2视频 3文件。
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_ATTACH_EXT:
        raise ParamError("不支持的文件格式（支持图片/视频/pdf/zip/word/excel/txt/md）")

    day_dir = UPLOAD_ROOT / date.today().isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    dest = day_dir / name

    content = _read_body(file, max_size)
    _assert_magic(content, ext)
    dest.write_bytes(content)

    if ext in (".mp4", ".mov", ".webm"):
        media_type = 2  # 视频
    elif ext in ALLOWED_EXT:
        media_type = 1  # 图片
    else:
        media_type = 3  # 文件
    return {
        "url": f"/uploads/{date.today().isoformat()}/{name}",
        "media_type": media_type,
        "file_size": len(content),
    }
