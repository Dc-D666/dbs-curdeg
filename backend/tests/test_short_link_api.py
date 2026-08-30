"""阶段5 API 测试：分享短链生成 / 跳转 / 计数防刷 / 过期（测试库 guild_test）。"""
import redis
import pytest

from app.core.config import settings
from app.models.short_link import ShortLink
from app.models.user import User
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


def _create_community(client, token: str, name: str = "短链测试频道") -> int:
    res = client.post("/api/v1/communities", json={"name": name}, headers=_auth(token))
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


def _create_post(client, token: str, cid: int, title: str = "短链测试帖") -> int:
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
def ctx(client):
    owner, owner_uid = _register(client, "shareowner", "shareowner@test.com")
    cid = _create_community(client, owner)
    pid = _create_post(client, owner, cid)
    return {"client": client, "owner": owner, "owner_uid": owner_uid, "cid": cid, "pid": pid}


# ---------- 生成 ----------


def test_create_share_requires_auth(ctx):
    client = ctx["client"]
    res = client.post("/api/v1/shares", json={"target_type": 2, "target_id": 1})
    assert res.status_code == 401


def test_create_post_share(ctx):
    client, owner, pid = ctx["client"], ctx["owner"], ctx["pid"]
    res = client.post("/api/v1/shares", json={"target_type": 2, "target_id": pid}, headers=_auth(owner))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert len(data["code"]) == 8
    assert data["url"] == f"/s/{data['code']}"


def test_create_share_rejects_missing_target(ctx):
    client, owner = ctx["client"], ctx["owner"]
    res = client.post("/api/v1/shares", json={"target_type": 2, "target_id": 99999999}, headers=_auth(owner))
    assert res.status_code == 404


def test_create_share_rejects_bad_type(ctx):
    client, owner, pid = ctx["client"], ctx["owner"], ctx["pid"]
    res = client.post("/api/v1/shares", json={"target_type": 9, "target_id": pid}, headers=_auth(owner))
    assert res.status_code == 400  # 字段校验失败统一 400+2001


# ---------- 跳转 ----------


def test_resolve_post_share_redirects(ctx):
    """GET /s/{code} → 302 /p/{pid}；两次不同 IP 访问计数 2（Redis 增量）。"""
    import redis as redis_lib

    client, owner, pid = ctx["client"], ctx["owner"], ctx["pid"]
    code = client.post("/api/v1/shares", json={"target_type": 2, "target_id": pid}, headers=_auth(owner)).json()["data"]["code"]
    res = client.get(f"/s/{code}", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == f"/p/{pid}"

    # 再次访问（不同 IP 头）计数 +1
    client.get(f"/s/{code}", follow_redirects=False, headers={"X-Forwarded-For": "1.2.3.4"})
    r = redis_lib.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    assert int(r.get(f"share:visits:{code}") or 0) == 2
    r.delete(f"share:visits:{code}", f"share:uv:{code}:testclient", f"share:uv:{code}:1.2.3.4")


def test_resolve_community_and_user_share(ctx):
    client, owner, cid, owner_uid = ctx["client"], ctx["owner"], ctx["cid"], ctx["owner_uid"]
    code_c = client.post("/api/v1/shares", json={"target_type": 1, "target_id": cid}, headers=_auth(owner)).json()["data"]["code"]
    assert client.get(f"/s/{code_c}", follow_redirects=False).headers["location"] == f"/c/{cid}"
    code_u = client.post("/api/v1/shares", json={"target_type": 3, "target_id": owner_uid}, headers=_auth(owner)).json()["data"]["code"]
    assert client.get(f"/s/{code_u}", follow_redirects=False).headers["location"] == f"/users/{owner_uid}"


def test_resolve_unknown_code_404(ctx):
    client = ctx["client"]
    assert client.get("/s/AbCdEfGh", follow_redirects=False).status_code == 404


def test_resolve_expired_share_404(db_session):
    """过期短链 → 404（service 层单测，同连接可见数据）。"""
    from datetime import datetime, timedelta

    from app.core.response import NotFoundError
    from app.services.share_service import resolve_share

    # FK 整改：creator_id 必须指向真实用户（原 creator_id=1 是不存在的哨兵）
    creator = User(username="shareuser1", email="shareuser1@test.com", password_hash="x")
    db_session.add(creator)
    db_session.flush()
    db_session.add(ShortLink(
        code="Expired1", target_type=2, target_id=1, creator_id=creator.id,
        expires_at=datetime.now() - timedelta(hours=1),
    ))
    db_session.commit()
    with pytest.raises(NotFoundError):
        resolve_share(db_session, "Expired1", None)


def test_visit_dedupe_same_ip(ctx):
    """同 IP 60s 内重复访问只计一次。"""
    import redis as redis_lib

    client, owner, pid = ctx["client"], ctx["owner"], ctx["pid"]
    code = client.post("/api/v1/shares", json={"target_type": 2, "target_id": pid}, headers=_auth(owner)).json()["data"]["code"]
    client.get(f"/s/{code}", follow_redirects=False, headers={"X-Forwarded-For": "9.9.9.9"})
    client.get(f"/s/{code}", follow_redirects=False, headers={"X-Forwarded-For": "9.9.9.9"})
    client.get(f"/s/{code}", follow_redirects=False, headers={"X-Forwarded-For": "9.9.9.9"})

    r = redis_lib.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    visits = int(r.get(f"share:visits:{code}") or 0)
    assert visits == 1  # 三次访问（同一 IP）只计一次
    # 清理 redis 测试键
    r.delete(f"share:visits:{code}", f"share:uv:{code}:9.9.9.9")


def test_cleanup_expired(db_session):
    """清理任务删除过期短链，保留未过期的。"""
    from datetime import datetime, timedelta

    from app.services.share_service import cleanup_expired

    creator = User(username="shareuser2", email="shareuser2@test.com", password_hash="x")
    db_session.add(creator)
    db_session.flush()
    db_session.add(ShortLink(code="CleanUp1", target_type=2, target_id=1, creator_id=creator.id,
                             expires_at=datetime.now() - timedelta(hours=2)))
    db_session.add(ShortLink(code="KeepAlive", target_type=2, target_id=1, creator_id=creator.id,
                             expires_at=datetime.now() + timedelta(hours=2)))
    db_session.commit()
    n = cleanup_expired(db_session)
    assert n == 1
    from sqlalchemy import select

    assert db_session.execute(select(ShortLink).where(ShortLink.code == "KeepAlive")).scalar_one() is not None
    assert db_session.execute(select(ShortLink).where(ShortLink.code == "CleanUp1")).scalar_one_or_none() is None
