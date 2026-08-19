"""阶段5 API 测试：Feed 热度（feed_strategies 权重 + Redis 缓存排序，测试库 guild_test）。

验收点：
- 热度策略 GET 默认值 / PUT 更新（member_manage 权限）/ 普通成员 403
- 热度排序按公式（like*1 + comment*2 + 时间衰减），与最新流可区分
- 点赞/评论后 bump 增量更新缓存排序
- 全站 hot 流可用
"""
import redis
import pytest

from app.core.config import settings
from app.services.email_service import CODE_PREFIX

HOT_ZKEY = "feed:hot:{cid}"


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


def _create_community(client, token: str, name: str = "热度测试频道") -> int:
    res = client.post("/api/v1/communities", json={"name": name}, headers=_auth(token))
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


def _create_post(client, token: str, cid: int, title: str, bid: int | None = None) -> int:
    if bid is None:
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


def _hot_ids(client, cid: int) -> list[int]:
    res = client.get(f"/api/v1/communities/{cid}/feed?sort=hot&page_size=50")
    assert res.status_code == 200, res.text
    return [p["id"] for p in res.json()["data"]["items"]]


def _clean_redis(cid: int):
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    r.delete(HOT_ZKEY.format(cid=cid), "feed:hot:all")


@pytest.fixture()
def ctx(client):
    """owner + normal（成员）+ 频道 + 版块。"""
    owner, _ = _register(client, "heatowner", "heatowner@test.com")
    normal, _ = _register(client, "heatnormal", "heatnormal@test.com")
    cid = _create_community(client, owner)
    bid = client.post(
        f"/api/v1/communities/{cid}/boards", json={"name": "闲聊", "description": ""},
        headers=_auth(owner),
    ).json()["data"]["id"]
    res = client.post(f"/api/v1/communities/{cid}/join", headers=_auth(normal))
    assert res.status_code == 200, res.text
    _clean_redis(cid)
    yield {"client": client, "owner": owner, "normal": normal, "cid": cid, "bid": bid}
    _clean_redis(cid)


# ---------- 策略配置 ----------


def test_strategy_defaults(ctx):
    client, owner, cid = ctx["client"], ctx["owner"], ctx["cid"]
    res = client.get(f"/api/v1/communities/{cid}/feed-strategy")
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["weight_like"] == 1
    assert data["weight_comment"] == 2
    assert data["weight_favorite"] == 3
    assert data["decay_hours"] == 24


def test_strategy_update_requires_manage_perm(ctx):
    client, normal, cid = ctx["client"], ctx["normal"], ctx["cid"]
    res = client.put(f"/api/v1/communities/{cid}/feed-strategy", json={"weight_comment": 5}, headers=_auth(normal))
    assert res.status_code == 403


def test_strategy_update_and_readback(ctx):
    client, owner, cid = ctx["client"], ctx["owner"], ctx["cid"]
    res = client.put(
        f"/api/v1/communities/{cid}/feed-strategy",
        json={"weight_comment": 5, "decay_hours": 12, "cache_ttl": 60},
        headers=_auth(owner),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["weight_comment"] == 5
    assert data["decay_hours"] == 12
    assert data["cache_ttl"] == 60
    # 未改的字段保持默认
    assert data["weight_like"] == 1


# ---------- 热度排序 ----------


def test_hot_feed_orders_by_heat_score(ctx):
    """A 帖 1 赞 vs B 帖 1 赞 + 2 评论 → B 热度分更高（comment 权重 2）。"""
    client, owner, normal, cid, bid = ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"], ctx["bid"]
    pa = _create_post(client, owner, cid, "A 帖", bid)
    pb = _create_post(client, owner, cid, "B 帖", bid)
    # A 1 赞；B 1 赞 + 2 评论
    client.post("/api/v1/likes", json={"post_id": pa}, headers=_auth(normal))
    client.post("/api/v1/likes", json={"post_id": pb}, headers=_auth(normal))
    for _ in range(2):
        client.post(f"/api/v1/posts/{pb}/comments", json={"content": "评论"}, headers=_auth(normal))

    ids = _hot_ids(client, cid)
    assert ids.index(pb) < ids.index(pa)  # B 在 A 前面


def test_hot_vs_latest_distinguishable(ctx):
    """同一数据下 hot 与 latest 顺序可区分（验收点 3）。

    注意：不直连 SessionLocal（那是生产库连接！），全部走 API 造数据。
    """
    client, owner, normal, cid, bid = ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"], ctx["bid"]
    p1 = _create_post(client, owner, cid, "旧帖", bid)  # 先发
    p2 = _create_post(client, owner, cid, "新帖", bid)  # 后发
    # 3 个临时成员点赞旧帖 → 旧帖热度更高；latest 依然新帖在前
    for i in range(3):
        t, _ = _register(client, f"heatold{i}", f"heatold{i}@test.com")
        client.post(f"/api/v1/communities/{cid}/join", headers=_auth(t))
        client.post("/api/v1/likes", json={"post_id": p1}, headers=_auth(t))
    _clean_redis(cid)

    hot = _hot_ids(client, cid)
    latest = client.get(f"/api/v1/communities/{cid}/feed?sort=latest&page_size=50").json()["data"]["items"]
    latest_ids = [p["id"] for p in latest]
    assert hot.index(p1) < hot.index(p2)              # hot：旧帖（3赞）在前
    assert latest_ids.index(p2) < latest_ids.index(p1)  # latest：新帖在前


def test_bump_updates_hot_order(ctx):
    """点赞后 bump 立即更新缓存排序（无需等 TTL）。"""
    client, owner, normal, cid, bid = ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"], ctx["bid"]
    pa = _create_post(client, owner, cid, "A 帖", bid)
    pb = _create_post(client, owner, cid, "B 帖", bid)
    # 先建立缓存：A 1 赞在前
    client.post("/api/v1/likes", json={"post_id": pa}, headers=_auth(normal))
    assert _hot_ids(client, cid)[0] == pa
    # B 加 5 赞 → B 应反超
    for _ in range(5):
        # 同一用户重复点赞无效，注册临时账号逐个赞
        t, _ = _register(client, f"heatfan{_}", f"heatfan{_}@test.com")
        client.post(f"/api/v1/communities/{cid}/join", headers=_auth(t))
        client.post("/api/v1/likes", json={"post_id": pb}, headers=_auth(t))
    ids = _hot_ids(client, cid)
    assert ids.index(pb) < ids.index(pa)


def test_global_hot_feed_works(ctx):
    client, owner, cid, bid = ctx["client"], ctx["owner"], ctx["cid"], ctx["bid"]
    _create_post(client, owner, cid, "全局热帖", bid)
    res = client.get("/api/v1/feed?sort=hot&page_size=20")
    assert res.status_code == 200, res.text
    assert res.json()["data"]["items"]  # 全站热度流有数据
