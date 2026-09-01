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
    assert len(data["boards"]) == 1  # 自动创建默认版块（保证立即可发帖）
    assert data["boards"][0]["name"] == "默认版块"


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
    # 列表可见（默认版块 + 新建 = 2）
    res2 = client.get(f"/api/v1/communities/{ctx['cid']}/boards")
    assert res2.status_code == 200
    assert len(res2.json()["data"]) == 2
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
    assert len(res6.json()["data"]) == 1  # 只剩默认版块


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


def test_rejected_join_can_reapply(ctx):
    """被拒后可重新申请（uq 约束与应用语义闭环，08-29 修复：原实现撞唯一键 500）。"""
    client = ctx["client"]
    cid = _create_community(client, ctx["owner"], "重申频道", join_setting=1)
    # 首次申请 → 拒绝
    res = client.post(f"/api/v1/communities/{cid}/join", headers=_auth(ctx["normal"]))
    assert res.status_code == 200
    reqs = client.get(f"/api/v1/communities/{cid}/join-requests", headers=_auth(ctx["owner"])).json()["data"]["items"]
    assert len(reqs) == 1
    res_rej = client.post(
        f"/api/v1/communities/{cid}/join-requests/{reqs[0]['id']}",
        json={"approve": False},
        headers=_auth(ctx["owner"]),
    )
    assert res_rej.status_code == 200
    # 被拒后重新申请 → 成功回到待审（不再撞 uq_joinreq_community_user）
    res2 = client.post(f"/api/v1/communities/{cid}/join", headers=_auth(ctx["normal"]))
    assert res2.status_code == 200
    assert res2.json()["data"]["status"] == "pending"
    # 仍只有一条申请记录（复用原行），状态已重置；重复申请依旧拦截
    reqs2 = client.get(f"/api/v1/communities/{cid}/join-requests", headers=_auth(ctx["owner"])).json()["data"]["items"]
    assert len(reqs2) == 1
    res3 = client.post(f"/api/v1/communities/{cid}/join", headers=_auth(ctx["normal"]))
    assert res3.status_code == 409


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


# ---------- 运营中心（频道主专属） ----------


def test_community_detail_exposes_perms_and_owner(ctx):
    """详情返回 my_perms/is_owner，供前端按权限显示管理/运营入口。"""
    client = ctx["client"]
    # 频道主：is_owner=True，my_perms 含全部权限点（super）
    data = client.get(f"/api/v1/communities/{ctx['cid']}", headers=_auth(ctx["owner"])).json()["data"]
    assert data["is_owner"] is True
    assert "super" in data["my_perms"]
    assert "member_manage" in data["my_perms"]
    # 普通成员加入后：非 owner，只有发帖/评论权限
    client.post(f"/api/v1/communities/{ctx['cid']}/join", headers=_auth(ctx["normal"]))
    data2 = client.get(f"/api/v1/communities/{ctx['cid']}", headers=_auth(ctx["normal"])).json()["data"]
    assert data2["is_owner"] is False
    assert "member_manage" not in data2["my_perms"]
    assert "post.create" in data2["my_perms"]


def test_ops_center_owner_only_and_data(ctx):
    """运营中心：频道主可见数据，普通成员 403，游客 401。"""
    client = ctx["client"]
    # 游客 401
    assert client.get(f"/api/v1/communities/{ctx['cid']}/ops-center").status_code == 401
    # 普通成员 403
    assert client.get(f"/api/v1/communities/{ctx['cid']}/ops-center", headers=_auth(ctx["normal"])).status_code == 403
    # 频道主 200 且结构完整
    res = client.get(f"/api/v1/communities/{ctx['cid']}/ops-center", headers=_auth(ctx["owner"]))
    assert res.status_code == 200, res.text
    d = res.json()["data"]
    assert "yesterday" in d and "today" in d and "user_data" in d
    assert "content_analysis" in d and "post_rank" in d
    assert d["user_data"]["total_members"] >= 1
    assert d["content_analysis"]["boards"], "应有默认版块的分析数据"


def test_ops_center_counts_join_leave_visit(ctx):
    """加入/访问事件被记录，运营中心能统计到（新增成员/访问次数）。"""
    client = ctx["client"]
    cid = ctx["cid"]
    # normal 加入 → 产生 join 事件
    client.post(f"/api/v1/communities/{cid}/join", headers=_auth(ctx["normal"]))
    # 访问打点 ×2
    client.post(f"/api/v1/communities/{cid}/visit", headers=_auth(ctx["normal"]))
    client.post(f"/api/v1/communities/{cid}/visit", headers=_auth(ctx["owner"]))
    d = client.get(f"/api/v1/communities/{cid}/ops-center", headers=_auth(ctx["owner"])).json()["data"]
    # join 事件：今日新增成员 >=1（normal）
    assert d["today"]["new_members"] >= 1
    # 访问次数 >=2（一次 normal + 一次 owner）
    assert d["user_data"]["all_visits"] >= 2
    # 访问人数（去重 user_id）>=2
    assert d["user_data"]["all_visitors"] >= 2
