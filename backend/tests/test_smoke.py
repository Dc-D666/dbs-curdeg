"""冒烟测试：应用可加载、健康检查可用（CI 用，不需要数据库）。"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz():
    res = client.get("/healthz")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["service"] == "channel-api"


def test_ping():
    res = client.get("/api/v1/ping")
    assert res.status_code == 200
    assert res.json() == {"message": "pong"}


def test_validation_error_friendly_hint():
    """字段校验失败返回友好中文提示（校验发生在 DB 依赖之前，无需数据库）。"""
    res = client.post("/api/v1/auth/register", json={
        "username": "中文用户名", "email": "hint@example.com", "code": "123456", "password": "pass123",
    })
    assert res.status_code == 400
    body = res.json()
    assert body["code"] == 2001
    assert "用户名" in body["message"]
    assert "下划线" in body["message"]


def test_validation_error_weak_password_hint():
    """密码不含字母/数字时给出具体原因。"""
    res = client.post("/api/v1/auth/register", json={
        "username": "okuser", "email": "hint@example.com", "code": "123456", "password": "abcdef",
    })
    assert res.status_code == 400
    body = res.json()
    assert body["code"] == 2001
    assert "字母和数字" in body["message"]
