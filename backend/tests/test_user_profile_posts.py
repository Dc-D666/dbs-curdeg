"""新增接口测试：管理后台成员关键词搜索 + 他人主页「TA 的帖子」。"""
import redis
import pytest

from app.core.config import settings
from app.services.email_service import CODE_PREFIX


def _seed_code(email: str, code: str = "123456"):
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    r.setex(f"{CODE_PREFIX}{email}", 300, code)


def _register(client, username: str, email: str, password: str = "pass123"):
    code = "123456"
    _seed_code(email, code)
    res = client.post("/api/v1/auth/register", json={
        "username": username, "email": email, "code": code, "password": password,
    })
    assert res.status_code == 200, res.text
    return res.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_community(client, token: str, name: str = "成员搜索频道", join_setting: int = 0) -> int:
    res = client.post("/api/v1/communities", json={"name": name, "join_setting": join_setting}, headers=_auth(token))
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


@pytest.fixture()
def ctx(client):
    """owner + 两个普通成员；owner 建频道并让两人加入。"""
    owner_token = _register(client, "owner_posts", "owner_posts@test.com")
    normal_a = _register(client, "alice_posts", "alice_posts@test.com")
    normal_b = _register(client, "bob_posts", "bob_posts@test.com")
    cid = _create_community(client, owner_token)
    for t in (normal_a, normal_b):
        client.post(f"/api/v1/communities/{cid}/join", headers=_auth(t))
    return {"client": client, "owner": owner_token, "a": normal_a, "b": normal_b, "cid": cid}


def test_members_keyword_search(ctx):
    """成员列表 keyword 过滤：命中用户名/昵称，非命中不返回。"""
    client = ctx["client"]
    # 无关键词返回全部成员（owner + 2）
    all_res = client.get(f"/api/v1/communities/{ctx['cid']}/members").json()["data"]
    assert all_res["total"] == 3

    # 命中 alice
    res = client.get(f"/api/v1/communities/{ctx['cid']}/members", params={"keyword": "alice"}).json()["data"]
    assert res["total"] == 1
    assert res["items"][0]["username"] == "alice_posts"

    # 命中昵称（未设置昵称时回退用户名），用不存在关键词验证为空
    res0 = client.get(f"/api/v1/communities/{ctx['cid']}/members", params={"keyword": "不存在xyz"}).json()["data"]
    assert res0["total"] == 0
    assert res0["items"] == []


def test_user_posts_interface(ctx):
    """用户发帖后，他人主页 /users/{id}/posts 可取到其最新帖子。"""
    client = ctx["client"]
    # alice 在默认版块发一帖
    cid = ctx["cid"]
    board_id = client.get(f"/api/v1/communities/{cid}").json()["data"]["boards"][0]["id"]
    post_res = client.post(
        f"/api/v1/communities/{cid}/boards/{board_id}/posts",
        json={"title": "Alice 的帖子", "content": "测试内容"},
        headers=_auth(ctx["a"]),
    )
    assert post_res.status_code == 200, post_res.text
    author_id = post_res.json()["data"]["author_id"]

    # 未登录也可读 TA 的帖子
    res = client.get(f"/api/v1/users/{author_id}/posts")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["items"]) >= 1
    assert any(p["id"] == post_res.json()["data"]["id"] for p in data["items"])

    # 用户不存在 → 404
    assert client.get("/api/v1/users/999999/posts").status_code == 404


def test_user_posts_excludes_deleted(ctx):
    """软删的帖子不应出现在 TA 的帖子流。"""
    client = ctx["client"]
    cid = ctx["cid"]
    board_id = client.get(f"/api/v1/communities/{cid}").json()["data"]["boards"][0]["id"]
    post_res = client.post(
        f"/api/v1/communities/{cid}/boards/{board_id}/posts",
        json={"title": "待删除", "content": "内容"},
        headers=_auth(ctx["a"]),
    )
    post_id = post_res.json()["data"]["id"]
    author_id = post_res.json()["data"]["author_id"]
    # 自己删除
    assert client.delete(f"/api/v1/posts/{post_id}", headers=_auth(ctx["a"])).status_code == 200
    data = client.get(f"/api/v1/users/{author_id}/posts").json()["data"]
    assert all(p["id"] != post_id for p in data["items"])
