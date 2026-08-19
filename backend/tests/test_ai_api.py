"""阶段6 API 测试：AI 帮写（SSE）/ RAG 问答 / 内容审核与申诉（LLM 全部 mock，测试库 guild_test）。

验收点：
- POST /ai/assist 返回 SSE 流（data: {"delta": ...} ... data: [DONE]）
- POST /ai/qa：语义召回 TopK 引用 + LLM 回答；embedding 落库缓存
- 发帖 → 快审通过 / 快审驳回（自动下架 + 通知 + reviews 落库）
- 申诉 → AI 复审通过恢复帖子；越权/重复申诉拦截

审核相关测试使用 client_ctx：请求与审核任务处理共享同一事务连接（数据互相可见）。
"""
import redis
import pytest

from app.core.config import settings
from app.models.post import Post, POST_STATUS_BANNED, POST_STATUS_NORMAL
from app.models.review import REVIEW_MANUAL, REVIEW_PASSED, REVIEW_REJECTED, Review
from app.services.email_service import CODE_PREFIX


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


def _create_community(client, token: str, name: str = "AI 测试频道") -> int:
    res = client.post("/api/v1/communities", json={"name": name}, headers=_auth(token))
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


def _create_board(client, token: str, cid: int) -> int:
    res = client.post(
        f"/api/v1/communities/{cid}/boards", json={"name": "版块", "description": ""},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


def _create_post(client, token: str, cid: int, bid: int, title: str, content: str = "内容") -> int:
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{bid}/posts",
        json={"title": title, "content": content, "images": []},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


@pytest.fixture()
def ctx(client):
    owner, owner_uid = _register(client, "aiowner", "aiowner@test.com")
    normal, normal_uid = _register(client, "ainormal", "ainormal@test.com")
    cid = _create_community(client, owner)
    bid = _create_board(client, owner, cid)
    res = client.post(f"/api/v1/communities/{cid}/join", headers=_auth(normal))
    assert res.status_code == 200, res.text
    return {"client": client, "owner": owner, "owner_uid": owner_uid,
            "normal": normal, "normal_uid": normal_uid, "cid": cid, "bid": bid}


@pytest.fixture()
def actx(client_ctx):
    """client + 同一连接 session（审核测试专用）。"""
    client, db = client_ctx
    owner, owner_uid = _register(client, "aictxowner", "aictxowner@test.com")
    normal, _ = _register(client, "aictxnormal", "aictxnormal@test.com")
    cid = _create_community(client, owner)
    bid = _create_board(client, owner, cid)
    res = client.post(f"/api/v1/communities/{cid}/join", headers=_auth(normal))
    assert res.status_code == 200, res.text
    return {"client": client, "db": db, "owner": owner, "owner_uid": owner_uid,
            "normal": normal, "cid": cid, "bid": bid}


# ---------- AI 帮写（SSE） ----------


def test_assist_sse_stream(ctx):
    client, owner = ctx["client"], ctx["owner"]
    res = client.post("/api/v1/ai/assist", json={"action": "write", "title": "周末爬山"}, headers=_auth(owner))
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/event-stream")
    body = res.text
    assert "data: " in body
    assert body.rstrip().endswith("data: [DONE]")
    # mock stream 的三个块都出现
    assert "AI 生成" in body and "内容" in body


def test_assist_requires_auth(ctx):
    client = ctx["client"]
    assert client.post("/api/v1/ai/assist", json={"action": "write"}).status_code == 401


# ---------- RAG 问答 ----------


def test_qa_returns_answer_and_references(ctx):
    client, owner, normal, cid, bid = ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"], ctx["bid"]
    pid1 = _create_post(client, owner, cid, bid, "爬山攻略", "泰山日出路线和装备清单")
    pid2 = _create_post(client, normal, cid, bid, "火锅推荐", "川渝火锅哪家强")

    res = client.post("/api/v1/ai/qa", json={"question": "周末去爬山有什么推荐"}, headers=_auth(normal))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert "测试回复" in data["answer"]
    assert data["references"], "应返回引用帖子"
    # 频道内只有 2 篇候选，TOP_K=5 全量返回
    ref_ids = {r["id"] for r in data["references"]}
    assert pid1 in ref_ids and pid2 in ref_ids
    assert len(data["references"]) <= 5


def test_qa_embeddings_cached(ctx, monkeypatch):
    """第二次问答不再调用 embedding API（列缓存生效）。"""
    from app.ai import llm_gateway

    client, owner, cid, bid = ctx["client"], ctx["owner"], ctx["cid"], ctx["bid"]
    _create_post(client, owner, cid, bid, "缓存测试帖", "缓存测试内容")
    calls = {"n": 0}
    orig = llm_gateway.embed

    def counting_embed(text):
        calls["n"] += 1
        return orig(text)

    monkeypatch.setattr(llm_gateway, "embed", counting_embed)
    client.post("/api/v1/ai/qa", json={"question": "第一个问题"}, headers=_auth(owner))
    first = calls["n"]
    assert first > 0
    client.post("/api/v1/ai/qa", json={"question": "第二个问题"}, headers=_auth(owner))
    # 第二次只对问题做 embedding，帖子向量全部命中缓存
    assert calls["n"] == first + 1


# ---------- 内容审核 ----------


def _process_manual(db, post_id):
    from app.ai.review import process_review_task

    return process_review_task(db, {"content_type": 1, "content_id": post_id})


def test_review_fast_pass(actx):
    """快审通过：生成 PASSED 记录，帖子保持正常。"""
    c, db, owner, cid, bid = actx["client"], actx["db"], actx["owner"], actx["cid"], actx["bid"]
    pid = _create_post(c, owner, cid, bid, "正常帖子", "今天天气不错")
    review = _process_manual(db, pid)
    assert review is not None
    assert review.status == REVIEW_PASSED
    assert review.result == "AI 快审通过"
    assert db.get(Post, pid).status == POST_STATUS_NORMAL


def test_review_fast_reject_bans_post(actx, monkeypatch):
    """快审驳回：自动下架 + reviews 落库 + 作者收到系统通知。"""
    from app.ai import llm_gateway
    from app.models.notification import Notification
    from sqlalchemy import select

    c, db, owner, owner_uid, cid, bid = (
        actx["client"], actx["db"], actx["owner"], actx["owner_uid"], actx["cid"], actx["bid"]
    )
    pid = _create_post(c, owner, cid, bid, "违规帖", "这里有违规内容")
    monkeypatch.setattr(
        llm_gateway, "chat",
        lambda messages, **kw: '{"pass": false, "type": "广告营销", "detail": "包含广告链接"}',
    )
    review = _process_manual(db, pid)
    assert review is not None
    assert review.status == REVIEW_REJECTED
    assert review.violation_type == "广告营销"
    assert db.get(Post, pid).status == POST_STATUS_BANNED

    n = db.execute(
        select(Notification).where(Notification.user_id == owner_uid, Notification.type == "system")
    ).scalar_one_or_none()
    assert n is not None
    assert "审核" in n.title


def test_appeal_restores_post(actx, monkeypatch):
    """申诉 → 复审通过 → 帖子恢复。"""
    from app.ai import llm_gateway

    c, db, owner, cid, bid = actx["client"], actx["db"], actx["owner"], actx["cid"], actx["bid"]
    pid = _create_post(c, owner, cid, bid, "被误判帖", "正常内容被误判")
    monkeypatch.setattr(
        llm_gateway, "chat",
        lambda messages, **kw: '{"pass": false, "type": "诈骗信息", "detail": "疑似诈骗"}',
    )
    review = _process_manual(db, pid)
    assert review.status == REVIEW_REJECTED
    assert db.get(Post, pid).status == POST_STATUS_BANNED

    # 申诉（复审 prompt → mock 返回 pass）
    monkeypatch.setattr(
        llm_gateway, "chat",
        lambda messages, **kw: '{"decision": "pass", "detail": "复审通过"}',
    )
    res = c.post(f"/api/v1/ai/reviews/{review.id}/appeal", headers=_auth(owner))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["status"] == REVIEW_PASSED
    assert "恢复" in data["result"]
    assert db.get(Post, pid).status == POST_STATUS_NORMAL


def test_appeal_manual_route(actx, monkeypatch):
    """复审转人工：status=MANUAL，帖子保持下架。"""
    from app.ai import llm_gateway

    c, db, owner, cid, bid = actx["client"], actx["db"], actx["owner"], actx["cid"], actx["bid"]
    pid = _create_post(c, owner, cid, bid, "边界内容", "边界案例内容")
    monkeypatch.setattr(
        llm_gateway, "chat",
        lambda messages, **kw: '{"pass": false, "type": "政治敏感", "detail": "疑似敏感"}',
    )
    review = _process_manual(db, pid)

    monkeypatch.setattr(
        llm_gateway, "chat",
        lambda messages, **kw: '{"decision": "manual", "detail": "需要人工判断"}',
    )
    res = c.post(f"/api/v1/ai/reviews/{review.id}/appeal", headers=_auth(owner))
    assert res.status_code == 200, res.text
    assert res.json()["data"]["status"] == REVIEW_MANUAL
    assert db.get(Post, pid).status == POST_STATUS_BANNED


def test_appeal_permissions(actx, monkeypatch):
    """越权申诉 403；重复申诉 400；未驳回不可申诉 400。"""
    from app.ai import llm_gateway

    c, db, owner, normal, cid, bid = (
        actx["client"], actx["db"], actx["owner"], actx["normal"], actx["cid"], actx["bid"]
    )
    pid = _create_post(c, owner, cid, bid, "申诉权限帖", "内容")
    monkeypatch.setattr(
        llm_gateway, "chat",
        lambda messages, **kw: '{"pass": false, "type": "其他", "detail": "x"}',
    )
    review = _process_manual(db, pid)

    assert c.post(f"/api/v1/ai/reviews/{review.id}/appeal", headers=_auth(normal)).status_code == 403
    assert c.post(f"/api/v1/ai/reviews/{review.id}/appeal", headers=_auth(owner)).status_code == 200
    assert c.post(f"/api/v1/ai/reviews/{review.id}/appeal", headers=_auth(owner)).status_code == 400

    pid2 = _create_post(c, owner, cid, bid, "正常帖2", "内容")
    monkeypatch.setattr(
        llm_gateway, "chat",
        lambda messages, **kw: '{"pass": true, "type": "", "detail": ""}',
    )
    passed = _process_manual(db, pid2)
    assert passed.status == REVIEW_PASSED
    assert c.post(f"/api/v1/ai/reviews/{passed.id}/appeal", headers=_auth(owner)).status_code == 400


def test_my_reviews_list(actx):
    c, db, owner, cid, bid = actx["client"], actx["db"], actx["owner"], actx["cid"], actx["bid"]
    pid = _create_post(c, owner, cid, bid, "列表帖", "内容")
    _process_manual(db, pid)
    res = c.get("/api/v1/ai/reviews/me", headers=_auth(owner))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["total"] >= 1
    assert data["items"][0]["content_id"] == pid
    assert data["items"][0]["status"] == REVIEW_PASSED
