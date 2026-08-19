"""auth API 集成测试（真实测试库 guild_test + TestClient）。

邮箱验证码在测试中直接写入 Redis（模拟用户已收到邮件），避免真实发信。
"""
import redis
import pytest

from app.core.config import settings
from app.services.email_service import CODE_PREFIX


def _seed_code(email: str, code: str = "123456"):
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    r.setex(f"{CODE_PREFIX}{email}", 300, code)


@pytest.fixture()
def auth_client(client):
    """带注册登录能力的客户端。"""
    return client


def _register(client, username="testuser", email="test@example.com", password="pass123", code="123456"):
    _seed_code(email, code)
    res = client.post("/api/v1/auth/register", json={
        "username": username, "email": email, "code": code, "password": password,
    })
    return res


def test_register_success(auth_client):
    res = _register(auth_client)
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"


def test_register_wrong_code(auth_client):
    _seed_code("wrong@example.com", "999999")
    res = auth_client.post("/api/v1/auth/register", json={
        "username": "user2", "email": "wrong@example.com", "code": "000000", "password": "pass123",
    })
    assert res.status_code == 400
    assert res.json()["code"] == 2001


def test_register_duplicate(auth_client):
    _register(auth_client, username="dupuser", email="dup@example.com")
    res = _register(auth_client, username="dupuser", email="dup@example.com")
    assert res.status_code == 409
    assert res.json()["code"] == 2002


def test_register_weak_password(auth_client):
    _seed_code("weak@example.com", "123456")
    res = auth_client.post("/api/v1/auth/register", json={
        "username": "weakuser", "email": "weak@example.com", "code": "123456", "password": "abcdef",
    })
    assert res.status_code == 400  # 统一参数校验错误（HTTP 400 + code 2001）
    assert res.json()["code"] == 2001


def test_login_and_refresh(auth_client):
    _register(auth_client, username="loginuser", email="login@example.com", password="pass123")
    # 用户名登录
    res = auth_client.post("/api/v1/auth/login", json={"account": "loginuser", "password": "pass123"})
    assert res.status_code == 200
    tokens = res.json()["data"]
    # 邮箱登录
    res2 = auth_client.post("/api/v1/auth/login", json={"account": "login@example.com", "password": "pass123"})
    assert res2.status_code == 200
    # 错误密码
    res3 = auth_client.post("/api/v1/auth/login", json={"account": "loginuser", "password": "wrongpw"})
    assert res3.status_code == 401
    assert res3.json()["code"] == 1001
    # 刷新
    res4 = auth_client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res4.status_code == 200
    assert res4.json()["data"]["access_token"]


def test_me_requires_auth(auth_client):
    res = auth_client.get("/api/v1/users/me")
    assert res.status_code == 401


def test_me_and_update_profile(auth_client):
    _register(auth_client, username="profileuser", email="profile@example.com")
    login = auth_client.post("/api/v1/auth/login", json={"account": "profileuser", "password": "pass123"})
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # 我的资料
    res = auth_client.get("/api/v1/users/me", headers=headers)
    assert res.status_code == 200
    me = res.json()["data"]
    assert me["username"] == "profileuser"
    # 改资料
    res2 = auth_client.put("/api/v1/users/me", headers=headers, json={"nickname": "新昵称", "bio": "你好", "gender": 1})
    assert res2.status_code == 200
    assert res2.json()["data"]["nickname"] == "新昵称"
    # 他人主页
    res3 = auth_client.get(f"/api/v1/users/{me['id']}")
    assert res3.status_code == 200


def test_change_password(auth_client):
    _register(auth_client, username="changepw", email="changepw@example.com")
    login = auth_client.post("/api/v1/auth/login", json={"account": "changepw", "password": "pass123"})
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # 改密成功
    res = auth_client.put("/api/v1/auth/password", headers=headers, json={"old_password": "pass123", "new_password": "newpass456"})
    assert res.status_code == 200
    # 旧密码失效
    res2 = auth_client.post("/api/v1/auth/login", json={"account": "changepw", "password": "pass123"})
    assert res2.status_code == 401
    # 新密码可登录
    res3 = auth_client.post("/api/v1/auth/login", json={"account": "changepw", "password": "newpass456"})
    assert res3.status_code == 200


def test_logout_invalidates_refresh(auth_client):
    _register(auth_client, username="logoutuser", email="logout@example.com")
    login = auth_client.post("/api/v1/auth/login", json={"account": "logoutuser", "password": "pass123"})
    refresh_token = login.json()["data"]["refresh_token"]
    res = auth_client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert res.status_code == 200
    # 登出后 refresh 失效
    res2 = auth_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert res2.status_code == 401
