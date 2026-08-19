"""阶段2 API 测试：频道/版块/成员/加入审核（测试库 guild_test）。"""
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


def _create_community(client, token: str, name: str = "测试频道", join_setting: int = 0) -> int:
    res = client.post("/api/v1/communities", json={"name": name, "join_setting": join_setting}, headers=_auth(token))
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


@pytest.fixture()
def ctx(client):
    """两个用户：owner + normal，owner 建好频道。"""
    owner_token = _register(client, "owner1", "owner1@test.com")
    normal_token = _register(client, "normal1", "normal1@test.com")
    cid = _create_community(client, owner_token, "测试频道")
    return {"client": client, "owner": owner_token, "normal": normal_token, "cid": cid}


def test_create_community_initializes_roles_and_member(ctx):
    client = ctx["client"]
    res = client.get(f"/api/v1/communities/{ctx['cid']}", headers=_auth(ctx["owner"]))
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["name"] == "测试频道"
    assert data["is_member"] is True
    assert data["my_member_type"] == 0  # owner
    assert data["member_count"] == 1
    assert data["number"]  # 频道号非空


def test_join_free_community(ctx):
    client = ctx["client"]
    res = client.post(f"/api/v1/communities/{ctx['cid']}/join", headers=_auth(ctx["normal"]))
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "joined"
    # 成员数 +1
    detail = client.get(f"/api/v1/communities/{ctx['cid']}").json()["data"]
    assert detail["member_count"] == 2
    # 重复加入冲突
    res2 = client.post(f"/api/v1/communities/{ctx['cid']}/join", headers=_auth(ctx["normal"]))
    assert res2.status_code == 409


def test_join_requires_login(ctx):
    client = ctx["client"]
    res = client.post(f"/api/v1/communities/{ctx['cid']}/join")
    assert res.status_code == 401


def test_board_crud_only_owner(ctx):
    client = ctx["client"]
    # owner 建版块
    res = client.post(
        f"/api/v1/communities/{ctx['cid']}/boards",
        json={"name": "闲聊", "description": "灌水区"},
        headers=_auth(ctx["owner"]),
    )
    assert res.status_code == 200, res.text
    board_id = res.json()["data"]["id"]
    # 列表可见
    res2 = client.get(f"/api/v1/communities/{ctx['cid']}/boards")
    assert res2.status_code == 200
    assert len(res2.json()["data"]) == 1
    # 普通成员不能建版块
    res3 = client.post(
        f"/api/v1/communities/{ctx['cid']}/boards",
        json={"name": "越权版块"},
        headers=_auth(ctx["normal"]),
    )
    assert res3.status_code == 403
    # owner 编辑
    res4 = client.put(
        f"/api/v1/communities/{ctx['cid']}/boards/{board_id}",
        json={"description": "改过的描述"},
        headers=_auth(ctx["owner"]),
    )
    assert res4.status_code == 200
    assert res4.json()["data"]["description"] == "改过的描述"
    # owner 删除（软删）
    res5 = client.delete(f"/api/v1/communities/{ctx['cid']}/boards/{board_id}", headers=_auth(ctx["owner"]))
    assert res5.status_code == 200
    res6 = client.get(f"/api/v1/communities/{ctx['cid']}/boards")
    assert len(res6.json()["data"]) == 0


def test_reviewed_join_flow(ctx):
    client = ctx["client"]
    # 审核制频道：owner 建；normal 申请
    cid = _create_community(client, ctx["owner"], "审核频道", join_setting=1)
    res = client.post(f"/api/v1/communities/{cid}/join", headers=_auth(ctx["normal"]))
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "pending"
    # 重复申请冲突
    res2 = client.post(f"/api/v1/communities/{cid}/join", headers=_auth(ctx["normal"]))
    assert res2.status_code == 409
    # owner 查申请
    res3 = client.get(f"/api/v1/communities/{cid}/join-requests", headers=_auth(ctx["owner"]))
    assert res3.status_code == 200
    reqs = res3.json()["data"]["items"]
    assert len(reqs) == 1
    assert reqs[0]["username"] == "normal1"
    # 普通成员无权审核
    res4 = client.get(f"/api/v1/communities/{cid}/join-requests", headers=_auth(ctx["normal"]))
    assert res4.status_code == 403
    # 通过
    res5 = client.post(
        f"/api/v1/communities/{cid}/join-requests/{reqs[0]['id']}",
        json={"approve": True},
        headers=_auth(ctx["owner"]),
    )
    assert res5.status_code == 200
    # 成员数 +1，normal 现在是成员
    detail = client.get(f"/api/v1/communities/{cid}").json()["data"]
    assert detail["member_count"] == 2
    member_list = client.get(f"/api/v1/communities/{cid}/members").json()["data"]["items"]
    assert any(m["username"] == "normal1" for m in member_list)


def test_invite_only_community_rejects(ctx):
    client = ctx["client"]
    cid = _create_community(client, ctx["owner"], "邀请频道", join_setting=2)
    res = client.post(f"/api/v1/communities/{cid}/join", headers=_auth(ctx["normal"]))
    assert res.status_code == 403


def test_leave_community(ctx):
    client = ctx["client"]
    client.post(f"/api/v1/communities/{ctx['cid']}/join", headers=_auth(ctx["normal"]))
    res = client.post(f"/api/v1/communities/{ctx['cid']}/leave", headers=_auth(ctx["normal"]))
    assert res.status_code == 200
    # owner 不能退出
    res2 = client.post(f"/api/v1/communities/{ctx['cid']}/leave", headers=_auth(ctx["owner"]))
    assert res2.status_code == 403


def test_dissolve_only_owner(ctx):
    client = ctx["client"]
    # normal 无权解散
    res = client.delete(f"/api/v1/communities/{ctx['cid']}", headers=_auth(ctx["normal"]))
    assert res.status_code == 403
    # owner 解散
    res2 = client.delete(f"/api/v1/communities/{ctx['cid']}", headers=_auth(ctx["owner"]))
    assert res2.status_code == 200
    # 解散后详情不可见
    res3 = client.get(f"/api/v1/communities/{ctx['cid']}")
    assert res3.status_code == 404


def test_update_community_only_owner(ctx):
    client = ctx["client"]
    res = client.put(
        f"/api/v1/communities/{ctx['cid']}",
        json={"profile": "新的简介"},
        headers=_auth(ctx["owner"]),
    )
    assert res.status_code == 200
    assert res.json()["data"]["profile"] == "新的简介"
    res2 = client.put(
        f"/api/v1/communities/{ctx['cid']}",
        json={"profile": "越权"},
        headers=_auth(ctx["normal"]),
    )
    assert res2.status_code == 403
