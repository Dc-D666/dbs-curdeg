"""上传服务：图片保存到共享卷 /app/uploads，nginx 直服 /uploads/。"""
import uuid
from datetime import date
from pathlib import Path

from fastapi import UploadFile

from app.core.response import ParamError

UPLOAD_ROOT = Path("/app/uploads")
ALLOWED_EXT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
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
