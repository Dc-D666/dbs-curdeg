"""阶段2补充测试：上传、频道状态调整、头像。"""
import io
import redis
import pytest

from app.core.config import settings
from app.services.email_service import CODE_PREFIX


def _seed_code(email: str, code: str = "123456"):
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    r.setex(f"{CODE_PREFIX}{email}", 300, code)


def _register(client, username: str, email: str):
    _seed_code(email)
    res = client.post("/api/v1/auth/register", json={
        "username": username, "email": email, "code": "123456", "password": "abc12345",
    })
    assert res.status_code == 200, res.text
    return res.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _png_bytes() -> bytes:
    # 最小合法 PNG
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
    )


@pytest.fixture()
def ctx(client):
    owner = _register(client, "ow2", "ow2@test.com")
    return {"client": client, "owner": owner}


def test_upload_image_requires_auth(ctx):
    res = ctx["client"].post("/api/v1/uploads", files={"file": ("a.png", _png_bytes(), "image/png")})
    assert res.status_code == 401


def test_upload_image_ok(ctx):
    res = ctx["client"].post(
        "/api/v1/uploads",
        files={"file": ("a.png", _png_bytes(), "image/png")},
        headers=_auth(ctx["owner"]),
    )
    assert res.status_code == 200, res.text
    url = res.json()["data"]["url"]
    assert url.startswith("/uploads/")
    assert url.endswith(".png")


def test_upload_rejects_bad_type(ctx):
    res = ctx["client"].post(
        "/api/v1/uploads",
        files={"file": ("a.exe", b"MZ...", "application/octet-stream")},
        headers=_auth(ctx["owner"]),
    )
    assert res.status_code == 400
    assert res.json()["code"] == 2001


def test_user_avatar_upload(ctx):
    res = ctx["client"].post(
        "/api/v1/users/me/avatar",
        files={"file": ("avatar.png", _png_bytes(), "image/png")},
        headers=_auth(ctx["owner"]),
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["avatar_url"].startswith("/uploads/")


def test_community_status_adjust(ctx):
    client = ctx["client"]
    # 建频道
    res = client.post("/api/v1/communities", json={"name": "状态测试"}, headers=_auth(ctx["owner"]))
    cid = res.json()["data"]["id"]
    # owner 关闭
    res2 = client.put(f"/api/v1/communities/{cid}/status", json={"status": 1}, headers=_auth(ctx["owner"]))
    assert res2.status_code == 200
    assert res2.json()["data"]["status"] == 1
    # owner 恢复
    res3 = client.put(f"/api/v1/communities/{cid}/status", json={"status": 0}, headers=_auth(ctx["owner"]))
    assert res3.status_code == 200
    # 违规封禁需要系统管理员
    res4 = client.put(f"/api/v1/communities/{cid}/status", json={"status": 2}, headers=_auth(ctx["owner"]))
    assert res4.status_code == 403


def test_community_avatar_and_cover_update(ctx):
    client = ctx["client"]
    res = client.post("/api/v1/communities", json={"name": "头像频道"}, headers=_auth(ctx["owner"]))
    cid = res.json()["data"]["id"]
    # 先上传图片拿 URL
    up = client.post(
        "/api/v1/uploads",
        files={"file": ("c.png", _png_bytes(), "image/png")},
        headers=_auth(ctx["owner"]),
    )
    url = up.json()["data"]["url"]
    # 更新头像/封面
    res2 = client.put(
        f"/api/v1/communities/{cid}",
        json={"avatar_url": url, "cover_url": url},
        headers=_auth(ctx["owner"]),
    )
    assert res2.status_code == 200
    data = res2.json()["data"]
    assert data["avatar_url"] == url
    assert data["cover_url"] == url
