"""阶段7 API 测试：搜索语义召回融合（embedding 余弦补漏，LLM mock）。"""
import pytest

from app.core.config import settings
from app.services.email_service import CODE_PREFIX
import redis


def _seed_code(email: str, code: str = "123456"):
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    r.setex(f"{CODE_PREFIX}{email}", 300, code)


def _register(client, username: str, email: str, password: str = "pass123") -> tuple[str, int]:
    _seed_code(email)
    res = client.post("/api/v1/auth/register", json={
        "username": username, "email": email, "code": "123456", "password": password,
    })
    assert res.status_code == 200, res.text
    token = res.json()["data"]["access_token"]
    me = client.get("/api/v1/users/me", headers=_auth(token))
    return token, me.json()["data"]["id"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def actx(client_ctx):
    """client + 同一连接 session（搜索语义测试）。"""
    client, db = client_ctx
    owner, _ = _register(client, "semowner", "semowner@test.com")
    cid = client.post("/api/v1/communities", json={"name": "语义搜索频道"}, headers=_auth(owner)).json()["data"]["id"]
    bid = client.post(
        f"/api/v1/communities/{cid}/boards", json={"name": "版块", "description": ""},
        headers=_auth(owner),
    ).json()["data"]["id"]
    return {"client": client, "db": db, "owner": owner, "cid": cid, "bid": bid}


def test_semantic_recall_fills_keyword_gap(actx, monkeypatch):
    """关键词搜不到但语义相近的帖子被召回（embedding 余弦补漏）。"""
    from sqlalchemy import select

    from app.ai import llm_gateway
    from app.models.post import Post

    client, db, owner, cid, bid = actx["client"], actx["db"], actx["owner"], actx["cid"], actx["bid"]
    # 发一篇与"泰山日出"完全无关字面的帖子
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{bid}/posts",
        json={"title": "周末爬山计划", "content": "准备去泰山看日出", "images": []},
        headers=_auth(owner),
    )
    pid = res.json()["data"]["id"]
    # 直接给帖子写入 embedding 向量 [1,0,0]（模拟已构建；优化 08-29 后向量在独立表）
    from app.models.post_embedding import PostEmbedding
    db.add(PostEmbedding(post_id=pid, vector=[1.0, 0.0, 0.0]))
    db.commit()

    # query 向量与帖子相同 → 余弦 = 1.0
    monkeypatch.setattr(llm_gateway, "embed", lambda text: [1.0, 0.0, 0.0])

    res = client.get(f"/api/v1/search/posts?q=日出推荐&community_id={cid}")
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    ids = [x["id"] for x in data["items"]]
    assert pid in ids, "语义召回应补漏到帖子"
