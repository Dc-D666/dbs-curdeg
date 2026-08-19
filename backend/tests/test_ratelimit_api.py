"""阶段7 API 测试：接口限流（429 + 3001）。"""
import redis
import pytest

from app.core.config import settings
from app.services.email_service import CODE_PREFIX


def _seed_code(email: str, code: str = "123456"):
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    r.setex(f"{CODE_PREFIX}{email}", 300, code)


def _register(client, username: str, email: str, password: str = "pass123"):
    _seed_code(email)
    res = client.post("/api/v1/auth/register", json={
        "username": username, "email": email, "code": "123456", "password": password,
    })
    assert res.status_code == 200, res.text
    return res.json()["data"]


@pytest.fixture()
def rl_enabled(monkeypatch):
    """本测试文件单独开启限流（conftest 默认关闭）。"""
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    yield
    # 清理限流键
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    for k in r.keys("rl:login:*") + r.keys("rl:register:*"):
        r.delete(k)


def test_login_rate_limited(client, rl_enabled):
    """同 IP 1 分钟 20 次登录上限：第 21 次 429。"""
    _register(client, "rluser", "rluser@test.com")
    code_429 = None
    for i in range(21):
        res = client.post("/api/v1/auth/login", json={"account": "rluser", "password": "wrong-pass"})
        if res.status_code == 429:
            code_429 = res.status_code
            assert res.json()["code"] == 3001
            break
    assert code_429 == 429, "第 21 次登录应被限流"
