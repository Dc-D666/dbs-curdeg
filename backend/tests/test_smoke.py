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
