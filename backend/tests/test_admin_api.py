"""阶段7 API 测试：运营看板 / 审核管理（系统管理员），测试库 guild_test。"""
import redis
import pytest

from app.core.config import settings
from app.models.review import REVIEW_MANUAL, REVIEW_PASSED, REVIEW_REJECTED
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


def _create_community(client, token: str, name: str = "看板测试频道") -> int:
    res = client.post("/api/v1/communities", json={"name": name}, headers=_auth(token))
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


def _create_post(client, token: str, cid: int, title: str = "看板帖") -> int:
    bid = client.post(
        f"/api/v1/communities/{cid}/boards", json={"name": "版块", "description": ""},
        headers=_auth(token),
    ).json()["data"]["id"]
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{bid}/posts",
        json={"title": title, "content": "内容", "images": []},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


@pytest.fixture()
def actx(client_ctx):
    """client + 同一连接 session；owner 提升为系统管理员。"""
    client, db = client_ctx
    owner, owner_uid = _register(client, "admowner", "admowner@test.com")
    normal, normal_uid = _register(client, "admnormal", "admnormal@test.com")
    cid = _create_community(client, owner)
    pid = _create_post(client, owner, cid)
    # 提升 owner 为系统管理员（user_type=1）
    from app.models.user import User

    u = db.get(User, owner_uid)
    u.user_type = 1
    db.commit()
    return {"client": client, "db": db, "owner": owner, "owner_uid": owner_uid,
            "normal": normal, "normal_uid": normal_uid, "cid": cid, "pid": pid}


# ---------- 权限 ----------


def test_stats_requires_admin(actx):
    c, normal = actx["client"], actx["normal"]
    assert c.get("/api/v1/admin/stats", headers=_auth(normal)).status_code == 403


def test_stats_overview(actx):
    c, owner = actx["client"], actx["owner"]
    res = c.get("/api/v1/admin/stats", headers=_auth(owner))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["users_total"] >= 2
    assert data["communities_total"] >= 1
    assert data["posts_total"] >= 1
    assert data["comments_total"] >= 0
    assert data["likes_total"] >= 0
    assert isinstance(data["posts_trend_7d"], list)
    assert data["top_communities"], "应有 Top 频道"
    assert data["top_communities"][0]["posts"] >= 1


# ---------- 平台级频道/用户列表（平台控制台首页） ----------


def test_admin_communities_lists_all_including_banned(actx):
    """平台管理员可见全部频道（含被封），普通用户无权访问。"""
    c, owner, normal, cid = actx["client"], actx["owner"], actx["normal"], actx["cid"]
    # 普通用户无平台权限
    assert c.get("/api/v1/admin/communities", headers=_auth(normal)).status_code == 403
    # 平台管理员：能看到自己创建的这个频道
    res = c.get("/api/v1/admin/communities", headers=_auth(owner))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["total"] >= 1
    ch = next(x for x in data["items"] if x["id"] == cid)
    assert ch["member_count"] >= 1
    assert ch["post_count"] >= 1
    assert ch["status"] == 0
    assert "owner_name" in ch
    assert "active_members" in ch
    # 封禁该频道后，平台列表仍应能看到它且 status=2（公开列表看不到）
    r = c.put(f"/api/v1/communities/{cid}/status", json={"status": 2}, headers=_auth(owner))
    assert r.status_code == 200, r.text
    res = c.get("/api/v1/admin/communities?status=2", headers=_auth(owner))
    data = res.json()["data"]
    assert any(x["id"] == cid and x["status"] == 2 for x in data["items"])


def test_admin_users_lists_all_and_filter(actx):
    """平台管理员可见全部用户（含封禁/注销），普通用户无权，封禁后仍可见。"""
    c, owner, normal, normal_uid = actx["client"], actx["owner"], actx["normal"], actx["normal_uid"]
    assert c.get("/api/v1/admin/users", headers=_auth(normal)).status_code == 403
    res = c.get("/api/v1/admin/users", headers=_auth(owner))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["total"] >= 2
    u = next(x for x in data["items"] if x["id"] == normal_uid)
    assert u["status"] == 0
    assert u["user_type"] == 0
    assert "joined_communities" in u
    # 封禁该普通用户
    r = c.put(f"/api/v1/admin/users/{normal_uid}/status", json={"status": 1}, headers=_auth(owner))
    assert r.status_code == 200, r.text
    res = c.get("/api/v1/admin/users?status=1", headers=_auth(owner))
    data = res.json()["data"]
    assert any(x["id"] == normal_uid and x["status"] == 1 for x in data["items"])
    # 搜索命中
    res = c.get("/api/v1/admin/users?keyword=admnormal", headers=_auth(owner))
    data = res.json()["data"]
    assert any(x["id"] == normal_uid for x in data["items"])


# ---------- 审核管理 ----------


def _make_manual_review(db, actx, monkeypatch, pid):
    """快审驳回 → 申诉转人工，得到 MANUAL 状态的记录。"""
    from app.ai import llm_gateway
    from app.ai.review import process_review_task

    monkeypatch.setattr(
        llm_gateway, "chat",
        lambda messages, **kw: '{"pass": false, "type": "政治敏感", "detail": "边界内容"}',
    )
    review = process_review_task(db, {"content_type": 1, "content_id": pid})
    monkeypatch.setattr(
        llm_gateway, "chat",
        lambda messages, **kw: '{"decision": "manual", "detail": "需要人工判断"}',
    )
    c, owner = actx["client"], actx["owner"]
    res = c.post(f"/api/v1/ai/reviews/{review.id}/appeal", headers=_auth(owner))
    assert res.status_code == 200, res.text
    assert res.json()["data"]["status"] == REVIEW_MANUAL
    return review


def test_admin_reviews_list_and_handle_approve(actx, monkeypatch):
    """管理员处理转人工复审：通过 → 帖子恢复 + 作者收到通知。"""
    from sqlalchemy import select

    from app.models.notification import Notification
    from app.models.post import Post
    from app.models.review import Review

    c, db, owner, owner_uid, pid = (
        actx["client"], actx["db"], actx["owner"], actx["owner_uid"], actx["pid"]
    )
    review = _make_manual_review(db, actx, monkeypatch, pid)

    res = c.get("/api/v1/admin/reviews?status=3", headers=_auth(owner))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["total"] >= 1
    assert any(r["id"] == review.id for r in data["items"])

    res = c.post(f"/api/v1/admin/reviews/{review.id}/handle", json={"approve": True}, headers=_auth(owner))
    assert res.status_code == 200, res.text
    n = db.execute(
        select(Notification).where(Notification.user_id == owner_uid, Notification.type == "system")
    ).scalars().all()
    assert any("人工复审" in x.title for x in n)
    db.expire_all()  # 同一连接不同 Session 的更新，刷新身份映射
    assert db.get(Post, pid).status == 0  # 恢复
    assert db.get(Review, review.id).status == REVIEW_PASSED


def test_admin_handle_reject_keeps_banned(actx, monkeypatch):
    from app.models.post import Post, POST_STATUS_BANNED

    c, db, owner, pid = actx["client"], actx["db"], actx["owner"], actx["pid"]
    review = _make_manual_review(db, actx, monkeypatch, pid)
    res = c.post(f"/api/v1/admin/reviews/{review.id}/handle", json={"approve": False}, headers=_auth(owner))
    assert res.status_code == 200, res.text
    assert db.get(Post, pid).status == POST_STATUS_BANNED
    from app.models.review import Review

    assert db.get(Review, review.id).status == REVIEW_REJECTED


def test_admin_handle_non_manual_rejected(actx, monkeypatch):
    """非转人工状态的记录不能人工处理。"""
    from app.ai import llm_gateway
    from app.ai.review import process_review_task

    c, db, owner, pid = actx["client"], actx["db"], actx["owner"], actx["pid"]
    monkeypatch.setattr(
        llm_gateway, "chat",
        lambda messages, **kw: '{"pass": false, "type": "广告", "detail": "广告"}',
    )
    review = process_review_task(db, {"content_type": 1, "content_id": pid})
    assert review.status == REVIEW_REJECTED
    res = c.post(f"/api/v1/admin/reviews/{review.id}/handle", json={"approve": True}, headers=_auth(owner))
    assert res.status_code == 400
