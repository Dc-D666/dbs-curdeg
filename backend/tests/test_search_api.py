"""阶段4 API 测试：关键词搜索（中文高亮/LIKE 兜底/频道过滤/热门词/记录落库）。

测试库无 FULLTEXT ngram 索引 → 自动走 LIKE 兜底路径，正好覆盖降级逻辑。
"""
import pytest


def _register(client, username: str, email: str) -> str:
    import redis

    from app.core.config import settings
    from app.services.email_service import CODE_PREFIX

    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    r.setex(f"{CODE_PREFIX}{email}", 300, "123456")
    res = client.post("/api/v1/auth/register", json={
        "username": username, "email": email, "code": "123456", "password": "pass123",
    })
    assert res.status_code == 200, res.text
    return res.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def ctx(client):
    """owner + 两个频道：A 有中文帖，B 有英文/数字帖。"""
    owner = _register(client, "searchowner", "searchowner@test.com")
    cid_a = client.post(
        "/api/v1/communities", json={"name": "搜索频道A", "join_setting": 0}, headers=_auth(owner)
    ).json()["data"]["id"]
    cid_b = client.post(
        "/api/v1/communities", json={"name": "搜索频道B", "join_setting": 0}, headers=_auth(owner)
    ).json()["data"]["id"]

    def _board(cid: int, name: str) -> int:
        return client.post(
            f"/api/v1/communities/{cid}/boards", json={"name": name, "description": ""},
            headers=_auth(owner),
        ).json()["data"]["id"]

    bid_a = _board(cid_a, "闲聊")
    bid_b = _board(cid_b, "科技")

    def _post(cid: int, bid: int, title: str, content: str) -> int:
        return client.post(
            f"/api/v1/communities/{cid}/boards/{bid}/posts",
            json={"title": title, "content": content, "images": []},
            headers=_auth(owner),
        ).json()["data"]["id"]

    post_weather = _post(cid_a, bid_a, "今天天气不错", "早上出门发现天气特别好，适合跑步")
    post_cat = _post(cid_a, bid_a, "小猫晒太阳", "我家小猫喜欢在阳台晒太阳睡觉")
    post_ai = _post(cid_b, bid_b, "SDUdiscord 课程设计", "FastAPI + Vue3 双端开发记录")
    return {"client": client, "owner": owner, "cid_a": cid_a, "cid_b": cid_b, "post_weather": post_weather,
            "post_cat": post_cat, "post_ai": post_ai}


def test_chinese_keyword_finds_post_with_highlight(ctx):
    """中文关键词能搜到帖子，标题带 <em class="hl"> 高亮。"""
    client = ctx["client"]
    res = client.get("/api/v1/search/posts", params={"q": "天气"})
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["total"] >= 1
    item = next(i for i in data["items"] if i["id"] == ctx["post_weather"])
    assert "<em class=\"hl\">天气</em>" in item["highlight_title"]
    assert "<em class=\"hl\">天气</em>" in item["snippet"]
    assert item["community_name"] == "搜索频道A"


def test_search_community_filter(ctx):
    """限定频道后只返回该频道帖子。"""
    client = ctx["client"]
    data = client.get("/api/v1/search/posts", params={"q": "天气", "community_id": ctx["cid_b"]}).json()["data"]
    assert data["total"] == 0
    data = client.get("/api/v1/search/posts", params={"q": "天气", "community_id": ctx["cid_a"]}).json()["data"]
    assert data["total"] >= 1


def test_like_fallback_for_english(ctx):
    """英文/数字关键词（测试库无 ngram 索引）走 LIKE 兜底也能搜到。"""
    client = ctx["client"]
    data = client.get("/api/v1/search/posts", params={"q": "SDUdiscord"}).json()["data"]
    assert data["total"] >= 1
    assert any(i["id"] == ctx["post_ai"] for i in data["items"])


def test_search_no_result_and_empty_query(ctx):
    client = ctx["client"]
    assert client.get("/api/v1/search/posts", params={"q": "不存在的词xyz"}).json()["data"]["total"] == 0
    assert client.get("/api/v1/search/posts", params={"q": ""}).status_code == 400


def test_hot_keywords_and_records(ctx):
    """搜索记录落库，热门词按次数统计。"""
    client = ctx["client"]
    for _ in range(3):
        client.get("/api/v1/search/posts", params={"q": "天气"})
    client.get("/api/v1/search/posts", params={"q": "小猫"})
    res = client.get("/api/v1/search/hot")
    assert res.status_code == 200, res.text
    hot = res.json()["data"]
    assert any(h["keyword"] == "天气" and h["count"] >= 3 for h in hot)
    assert any(h["keyword"] == "小猫" for h in hot)


def test_guest_search_allowed(ctx):
    """游客（无 token）可搜索。"""
    res = ctx["client"].get("/api/v1/search/posts", params={"q": "小猫"})
    assert res.status_code == 200, res.text
    assert res.json()["data"]["total"] >= 1
