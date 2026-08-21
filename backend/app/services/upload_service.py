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
MAX_SIZE = 5 * 1024 * 1024  # 5MB


def save_image(file: UploadFile) -> str:
    """保存图片，返回 URL 路径（如 /uploads/2026-08-19/xxxx.png）。"""
    if file.size and file.size > MAX_SIZE:
        raise ParamError("图片大小不能超过 5MB")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ParamError("仅支持 jpg/png/webp/gif 图片")

    # 目录按日期分片
    day_dir = UPLOAD_ROOT / date.today().isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)

    name = f"{uuid.uuid4().hex}{ext}"
    dest = day_dir / name

    content = file.file.read()
    if len(content) > MAX_SIZE:
        raise ParamError("图片大小不能超过 5MB")
    dest.write_bytes(content)

    return f"/uploads/{date.today().isoformat()}/{name}"


def save_attachment(file: UploadFile) -> dict:
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

    content = file.file.read()
    if len(content) > MAX_SIZE:
        raise ParamError("附件大小不能超过 5MB")
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
