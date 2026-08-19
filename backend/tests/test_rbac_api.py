"""阶段4 API 测试：身份组 RBAC 权限矩阵 / 管理动作 / op_log 留痕（测试库 guild_test）。

覆盖验收：管理员能置顶/删他人帖、普通成员不能（1002）；禁言到期自动解除；
被踢/拉黑成员无法再进频道发帖；管理动作 op_logs 留痕；越级防护。
"""
from datetime import datetime, timedelta

import pytest

from app.core.permissions import ALL_PERMS, get_member_perms
from app.core.response import PermissionError_
from app.models.community import Community
from app.models.member import MEMBER_NORMAL, Member
from app.models.user import User
from app.services import post_service

# ---------- 工具 ----------


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


def _create_community(client, token: str, name: str = "RBAC测试频道") -> int:
    res = client.post("/api/v1/communities", json={"name": name, "join_setting": 0}, headers=_auth(token))
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


def _create_board(client, token: str, cid: int) -> int:
    res = client.post(
        f"/api/v1/communities/{cid}/boards",
        json={"name": "闲聊", "description": ""},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


def _create_post(client, token: str, cid: int, bid: int, title: str = "测试帖") -> int:
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{bid}/posts",
        json={"title": title, "content": "正文内容", "images": []},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


def _get_role_id(client, token: str, cid: int, name: str) -> int:
    roles = client.get(f"/api/v1/communities/{cid}/roles", headers=_auth(token)).json()["data"]
    for r in roles:
        if r["name"] == name:
            return r["id"]
    raise AssertionError(f"身份组 {name} 不存在")


def _assign_role(client, token: str, cid: int, user_id: int, role_id: int) -> dict:
    res = client.post(
        f"/api/v1/communities/{cid}/members/{user_id}/role",
        json={"role_id": role_id},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]


@pytest.fixture()
def ctx(client):
    """owner + normal（已加入）+ 管理员（赋默认"管理员"身份组）+ 版块 + 帖子。"""
    owner = _register(client, "rbacowner", "rbacowner@test.com")
    normal = _register(client, "rbacnormal", "rbacnormal@test.com")
    admin = _register(client, "rbacadmin", "rbacadmin@test.com")
    cid = _create_community(client, owner)
    bid = _create_board(client, owner, cid)
    assert client.post(f"/api/v1/communities/{cid}/join", headers=_auth(normal)).status_code == 200
    assert client.post(f"/api/v1/communities/{cid}/join", headers=_auth(admin)).status_code == 200

    admin_id = client.get("/api/v1/users/me", headers=_auth(admin)).json()["data"]["id"]
    admin_role = _get_role_id(client, owner, cid, "管理员")
    _assign_role(client, owner, cid, admin_id, admin_role)

    post_id = _create_post(client, owner, cid, bid)
    return {"client": client, "owner": owner, "normal": normal, "admin": admin,
            "cid": cid, "bid": bid, "post_id": post_id, "admin_id": admin_id}


# ---------- 权限矩阵：置顶/精华/删他人帖 ----------


def test_normal_cannot_top(ctx):
    res = ctx["client"].post(f"/api/v1/posts/{ctx['post_id']}/top", headers=_auth(ctx["normal"]))
    assert res.status_code == 403
    assert res.json()["code"] == 1002


def test_admin_can_top(ctx):
    res = ctx["client"].post(f"/api/v1/posts/{ctx['post_id']}/top", headers=_auth(ctx["admin"]))
    assert res.status_code == 200, res.text
    assert res.json()["data"]["is_top"] is True


def test_normal_cannot_essence_but_admin_can(ctx):
    assert ctx["client"].post(
        f"/api/v1/posts/{ctx['post_id']}/essence", headers=_auth(ctx["normal"])
    ).status_code == 403
    res = ctx["client"].post(f"/api/v1/posts/{ctx['post_id']}/essence", headers=_auth(ctx["admin"]))
    assert res.status_code == 200, res.text
    assert res.json()["data"]["is_essence"] is True


def test_delete_others_post_requires_perm(ctx):
    """普通成员不能删他人帖；作者可删自己的；管理员可删他人的。"""
    client = ctx["client"]
    assert client.delete(f"/api/v1/posts/{ctx['post_id']}", headers=_auth(ctx["normal"])).status_code == 403
    # 管理员删除 owner 的帖子（他人）
    assert client.delete(f"/api/v1/posts/{ctx['post_id']}", headers=_auth(ctx["admin"])).status_code == 200
    # 作者本人仍可删自己的
    own = _create_post(client, ctx["owner"], ctx["cid"], ctx["bid"], title="自删帖")
    assert client.delete(f"/api/v1/posts/{own}", headers=_auth(ctx["owner"])).status_code == 200


# ---------- 权限矩阵：禁言/踢人 ----------


def test_normal_cannot_shutup_kick(ctx):
    client = ctx["client"]
    normal_id = client.get("/api/v1/users/me", headers=_auth(ctx["normal"])).json()["data"]["id"]
    assert client.post(
        f"/api/v1/communities/{ctx['cid']}/members/{normal_id}/shutup", json={"hours": 1},
        headers=_auth(ctx["normal"]),
    ).status_code == 403
    assert client.post(
        f"/api/v1/communities/{ctx['cid']}/members/{normal_id}/kick", headers=_auth(ctx["normal"])
    ).status_code == 403


def test_admin_can_shutup_and_blocked_user_cannot_post(ctx):
    client = ctx["client"]
    normal_id = client.get("/api/v1/users/me", headers=_auth(ctx["normal"])).json()["data"]["id"]
    res = client.post(
        f"/api/v1/communities/{ctx['cid']}/members/{normal_id}/shutup", json={"hours": 24},
        headers=_auth(ctx["admin"]),
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["shutup_expire_at"] is not None
    # 被禁言无法发帖
    res = client.post(
        f"/api/v1/communities/{ctx['cid']}/boards/{ctx['bid']}/posts",
        json={"title": "禁言期发帖", "content": "x"},
        headers=_auth(ctx["normal"]),
    )
    assert res.status_code == 403
    assert "禁言" in res.json()["message"]
    # 解除后恢复
    assert client.post(
        f"/api/v1/communities/{ctx['cid']}/members/{normal_id}/unshutup", headers=_auth(ctx["admin"])
    ).status_code == 200
    res = client.post(
        f"/api/v1/communities/{ctx['cid']}/boards/{ctx['bid']}/posts",
        json={"title": "解除后发帖", "content": "x"},
        headers=_auth(ctx["normal"]),
    )
    assert res.status_code == 200, res.text


def test_kick_blocks_rejoin_and_post(ctx):
    """被踢成员无法再进频道发帖，也无法重新加入。"""
    client = ctx["client"]
    normal_id = client.get("/api/v1/users/me", headers=_auth(ctx["normal"])).json()["data"]["id"]
    assert client.post(
        f"/api/v1/communities/{ctx['cid']}/members/{normal_id}/kick", headers=_auth(ctx["admin"])
    ).status_code == 200
    # 无法发帖
    res = client.post(
        f"/api/v1/communities/{ctx['cid']}/boards/{ctx['bid']}/posts",
        json={"title": "被踢后发帖", "content": "x"},
        headers=_auth(ctx["normal"]),
    )
    assert res.status_code == 403
    # 无法重新加入
    res = client.post(f"/api/v1/communities/{ctx['cid']}/join", headers=_auth(ctx["normal"]))
    assert res.status_code == 409
    assert "无法重新加入" in res.json()["message"]


def test_block_unblock(ctx):
    client = ctx["client"]
    normal_id = client.get("/api/v1/users/me", headers=_auth(ctx["normal"])).json()["data"]["id"]
    res = client.post(
        f"/api/v1/communities/{ctx['cid']}/members/{normal_id}/block", headers=_auth(ctx["admin"])
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["is_blocked"] is True
    # 普通成员无 member_manage，不能拉黑
    assert client.post(
        f"/api/v1/communities/{ctx['cid']}/members/{normal_id}/block", headers=_auth(ctx["normal"])
    ).status_code == 403
    # owner 解除
    res = client.post(
        f"/api/v1/communities/{ctx['cid']}/members/{normal_id}/unblock", headers=_auth(ctx["owner"])
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["is_blocked"] is False


# ---------- 越级防护 ----------


def test_admin_cannot_manage_owner(ctx):
    """管理员不能对频道主执行禁言/踢出/分配身份。"""
    client = ctx["client"]
    owner_id = client.get("/api/v1/users/me", headers=_auth(ctx["owner"])).json()["data"]["id"]
    assert client.post(
        f"/api/v1/communities/{ctx['cid']}/members/{owner_id}/shutup", json={"hours": 1},
        headers=_auth(ctx["admin"]),
    ).status_code == 403
    assert client.post(
        f"/api/v1/communities/{ctx['cid']}/members/{owner_id}/kick", headers=_auth(ctx["admin"])
    ).status_code == 403
    owner_role = _get_role_id(client, ctx["owner"], ctx["cid"], "频道主")
    assert client.post(
        f"/api/v1/communities/{ctx['cid']}/members/{owner_id}/role",
        json={"role_id": owner_role}, headers=_auth(ctx["admin"]),
    ).status_code == 403


def test_assign_role_level_guard(ctx):
    """越级分配：管理员不能分配 level >= 自身(50) 的身份组。"""
    client = ctx["client"]
    normal_id = client.get("/api/v1/users/me", headers=_auth(ctx["normal"])).json()["data"]["id"]
    admin_role = _get_role_id(client, ctx["owner"], ctx["cid"], "管理员")
    res = client.post(
        f"/api/v1/communities/{ctx['cid']}/members/{normal_id}/role",
        json={"role_id": admin_role}, headers=_auth(ctx["admin"]),
    )
    assert res.status_code == 403
    assert "等级" in res.json()["message"]
    # 管理员不能修改自己的身份
    assert client.post(
        f"/api/v1/communities/{ctx['cid']}/members/{ctx['admin_id']}/role",
        json={"role_id": None}, headers=_auth(ctx["admin"]),
    ).status_code == 403


def test_normal_cannot_assign_role(ctx):
    client = ctx["client"]
    admin_role = _get_role_id(client, ctx["owner"], ctx["cid"], "管理员")
    normal_id = client.get("/api/v1/users/me", headers=_auth(ctx["normal"])).json()["data"]["id"]
    res = client.post(
        f"/api/v1/communities/{ctx['cid']}/members/{normal_id}/role",
        json={"role_id": admin_role}, headers=_auth(ctx["normal"]),
    )
    assert res.status_code == 403


# ---------- 身份组 CRUD ----------


def test_roles_crud_permissions(ctx):
    """普通成员/管理员不能建身份组（role_manage 仅 owner）；owner 可建改删。"""
    client = ctx["client"]
    cid = ctx["cid"]
    body = {"name": "小编", "color": "#00b42a", "level": 30, "perms": ["post.create"]}
    assert client.post(f"/api/v1/communities/{cid}/roles", json=body, headers=_auth(ctx["normal"])).status_code == 403
    assert client.post(f"/api/v1/communities/{cid}/roles", json=body, headers=_auth(ctx["admin"])).status_code == 403

    res = client.post(f"/api/v1/communities/{cid}/roles", json=body, headers=_auth(ctx["owner"]))
    assert res.status_code == 200, res.text
    rid = res.json()["data"]["id"]

    # 非法权限点被拒绝
    res = client.post(
        f"/api/v1/communities/{cid}/roles",
        json={"name": "x", "perms": ["not_exist"]}, headers=_auth(ctx["owner"]),
    )
    assert res.status_code == 400
    assert "非法权限点" in res.json()["message"]

    # 更新
    res = client.put(
        f"/api/v1/communities/{cid}/roles/{rid}",
        json={"perms": ["post.create", "top"]}, headers=_auth(ctx["owner"]),
    )
    assert res.status_code == 200, res.text
    assert "top" in res.json()["data"]["perms"]

    # 删除自定义身份组 → 成员 role_id 清空
    normal_id = client.get("/api/v1/users/me", headers=_auth(ctx["normal"])).json()["data"]["id"]
    _assign_role(client, ctx["owner"], cid, normal_id, rid)
    assert client.delete(f"/api/v1/communities/{cid}/roles/{rid}", headers=_auth(ctx["owner"])).status_code == 200
    members = client.get(f"/api/v1/communities/{cid}/members", headers=_auth(ctx["owner"])).json()["data"]["items"]
    m = next(m for m in members if m["user_id"] == normal_id)
    assert m["role_id"] is None


def test_default_role_protected(ctx):
    """默认身份组不可删；频道主身份组不可改。"""
    client = ctx["client"]
    cid = ctx["cid"]
    admin_role = _get_role_id(client, ctx["owner"], cid, "管理员")
    assert client.delete(
        f"/api/v1/communities/{cid}/roles/{admin_role}", headers=_auth(ctx["owner"])
    ).status_code == 400
    owner_role = _get_role_id(client, ctx["owner"], cid, "频道主")
    res = client.put(
        f"/api/v1/communities/{cid}/roles/{owner_role}",
        json={"level": 1}, headers=_auth(ctx["owner"]),
    )
    assert res.status_code == 400
    assert "频道主身份组" in res.json()["message"]


# ---------- op_log 留痕 ----------


def test_ops_logged(ctx):
    """管理动作全部留痕，普通成员看不到日志。"""
    client = ctx["client"]
    cid = ctx["cid"]
    assert client.post(f"/api/v1/posts/{ctx['post_id']}/top", headers=_auth(ctx["admin"])).status_code == 200
    normal_id = client.get("/api/v1/users/me", headers=_auth(ctx["normal"])).json()["data"]["id"]
    assert client.post(
        f"/api/v1/communities/{cid}/members/{normal_id}/shutup", json={"hours": 1},
        headers=_auth(ctx["admin"]),
    ).status_code == 200
    # 普通成员无 moderate 权限
    assert client.get(f"/api/v1/communities/{cid}/ops", headers=_auth(ctx["normal"])).status_code == 403
    res = client.get(f"/api/v1/communities/{cid}/ops", headers=_auth(ctx["owner"]))
    assert res.status_code == 200, res.text
    actions = [item["action"] for item in res.json()["data"]["items"]]
    assert "set_top" in actions
    assert "shutup" in actions
    assert "assign_role" in actions  # 分配管理员身份时也留痕


# ---------- 系统管理员与禁言到期（服务层） ----------


def test_system_admin_full_perms(db_session):
    """系统管理员（user_type=1）即使非频道成员也拥有全部权限点。"""
    from app.core.permissions import require_perms

    u = User(username="sysadmin1", email="sysadmin1@test.com", password_hash="x", user_type=1)
    owner = User(username="sysowner1", email="sysowner1@test.com", password_hash="x")
    c = Community(number="SA1X2Y", name="系统测试频道", owner_id=0)
    db_session.add_all([u, owner, c])
    db_session.flush()
    m = Member(community_id=c.id, user_id=owner.id, member_type=0, nickname="o")
    db_session.add(m)
    db_session.commit()
    assert get_member_perms(db_session, c.id, u) == set(ALL_PERMS)
    assert require_perms(db_session, c.id, u, "top", "super") is None  # 非成员也放行


def test_shutup_expire_auto_unlock(db_session):
    """禁言到期自动解除：shutup_expire_at 已过则放行，未过则拒绝。"""
    u = User(username="shutupuser1", email="shutupuser1@test.com", password_hash="x")
    c = Community(number="SU1X2Y", name="禁言测试频道", owner_id=0)
    db_session.add_all([u, c])
    db_session.flush()
    m = Member(community_id=c.id, user_id=u.id, member_type=MEMBER_NORMAL, nickname="x")
    db_session.add(m)
    db_session.commit()

    # 已过期 → 放行
    m.shutup_expire_at = datetime.now() - timedelta(hours=1)
    db_session.commit()
    assert post_service._require_member(db_session, c.id, u.id) is m

    # 未过期 → 拒绝
    m.shutup_expire_at = datetime.now() + timedelta(hours=1)
    db_session.commit()
    with pytest.raises(PermissionError_):
        post_service._require_member(db_session, c.id, u.id)
