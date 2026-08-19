"""阶段5 API 测试：WebSocket 通知推送 / 通知列表已读 / 通知开关（测试库 guild_test）。

覆盖验收点：
- WS 认证（首帧 auth / 坏 token 4401 / 心跳 ping→pong / 断线清理）
- A 评论 B 的帖子 → B 在线时实时收到 notification（不刷新）
- 点赞 / 关注 / @提及 / 加入审核 / 禁言 → 落库通知
- 通知开关关闭后不再生成通知
"""
import redis
import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.services.email_service import CODE_PREFIX
from app.ws.manager import manager


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
    assert me.status_code == 200, me.text
    return token, me.json()["data"]["id"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_community(client, token: str, name: str = "通知测试频道", join_setting: int = 0) -> int:
    res = client.post("/api/v1/communities", json={"name": name, "join_setting": join_setting}, headers=_auth(token))
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


def _create_board(client, token: str, cid: int, name: str = "闲聊") -> int:
    res = client.post(f"/api/v1/communities/{cid}/boards", json={"name": name, "description": "测试版块"}, headers=_auth(token))
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


def _create_post(client, token: str, cid: int, bid: int, title: str = "通知测试帖", content: str = "帖子内容") -> int:
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{bid}/posts",
        json={"title": title, "content": content, "images": []},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


def _join(client, token: str, cid: int):
    res = client.post(f"/api/v1/communities/{cid}/join", headers=_auth(token))
    assert res.status_code == 200, res.text


def _comment(client, token: str, pid: int, content: str = "不错"):
    res = client.post(f"/api/v1/posts/{pid}/comments", json={"content": content}, headers=_auth(token))
    assert res.status_code == 200, res.text


def _notifications(client, token: str) -> list:
    res = client.get("/api/v1/notifications", headers=_auth(token))
    assert res.status_code == 200, res.text
    return res.json()["data"]["items"]


@pytest.fixture()
def ctx(client):
    """owner（帖子作者）+ normal（频道成员）。"""
    owner_token, owner_uid = _register(client, "ntfowner", "ntfowner@test.com")
    normal_token, normal_uid = _register(client, "ntfnormal", "ntfnormal@test.com")
    cid = _create_community(client, owner_token)
    bid = _create_board(client, owner_token, cid)
    _join(client, normal_token, cid)
    pid = _create_post(client, owner_token, cid, bid)
    return {
        "client": client, "owner": owner_token, "owner_uid": owner_uid,
        "normal": normal_token, "normal_uid": normal_uid,
        "cid": cid, "bid": bid, "pid": pid,
    }


# ---------- WebSocket：认证 / 心跳 / 断线 ----------


def test_ws_auth_and_ping_pong(ctx):
    """合法 token 首帧 auth → authed；ping → pong。"""
    client, owner = ctx["client"], ctx["owner"]
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": owner})
        assert ws.receive_json() == {"type": "authed"}
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def test_ws_rejects_invalid_token(client):
    """坏 token → 服务端 4401 断开。"""
    with pytest.raises(WebSocketDisconnect) as ei:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "auth", "token": "bad-token"})
            ws.receive_json()
    assert ei.value.code == 4401


def test_ws_requires_auth_first_message(client):
    """首帧不是 auth → 4401 断开。"""
    with pytest.raises(WebSocketDisconnect) as ei:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "ping"})
            ws.receive_json()
    assert ei.value.code == 4401


def test_ws_disconnect_cleanup(ctx):
    """断线后连接从 manager 清理（服务端收到断开是异步的，轮询等待）。"""
    import time

    client, owner = ctx["client"], ctx["owner"]
    before = manager.online_count()
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": owner})
        ws.receive_json()
        assert manager.online_count() == before + 1
    for _ in range(20):
        if manager.online_count() == before:
            break
        time.sleep(0.1)
    assert manager.online_count() == before


# ---------- WebSocket：实时推送（核心验收） ----------


def test_ws_realtime_comment_push(ctx):
    """normal 评论 owner 的帖子 → owner 在线时不刷新收到 notification。"""
    client, owner, normal, pid = ctx["client"], ctx["owner"], ctx["normal"], ctx["pid"]
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": owner})
        assert ws.receive_json() == {"type": "authed"}
        _comment(client, normal, pid, "实时推送测试")
        msg = ws.receive_json()
        assert msg["type"] == "notification"
        data = msg["data"]
        assert data["type"] == "comment"
        assert data["ref_id"] == pid
        assert data["title"]
        assert data["summary"] == "实时推送测试"


def test_ws_no_push_offline(ctx):
    """owner 不在线时评论 → 无推送（但通知落库，列表可见）。"""
    client, owner, normal, pid = ctx["client"], ctx["owner"], ctx["normal"], ctx["pid"]
    _comment(client, normal, pid, "离线评论")
    items = _notifications(client, owner)
    assert len(items) == 1
    assert items[0]["type"] == "comment"
    assert items[0]["is_read"] is False
    assert items[0]["actor_nickname"]  # 触发者昵称


# ---------- 通知落库触发点 ----------


def test_like_creates_notification(ctx):
    """normal 赞 owner 的帖子 → owner 收到 like 通知。"""
    client, owner, normal, pid = ctx["client"], ctx["owner"], ctx["normal"], ctx["pid"]
    res = client.post("/api/v1/likes", json={"post_id": pid}, headers=_auth(normal))
    assert res.status_code == 200, res.text
    items = _notifications(client, owner)
    assert len(items) == 1
    assert items[0]["type"] == "like"
    assert items[0]["ref_id"] == pid


def test_self_like_no_notification(ctx):
    """自己赞自己不产生通知。"""
    client, owner, pid = ctx["client"], ctx["owner"], ctx["pid"]
    res = client.post("/api/v1/likes", json={"post_id": pid}, headers=_auth(owner))
    assert res.status_code == 200, res.text
    assert _notifications(client, owner) == []


def test_follow_creates_notification(ctx):
    """normal 关注 owner 的频道 → owner 收到 follow 通知。"""
    client, owner, normal, cid = ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"]
    res = client.post("/api/v1/follows", json={"community_id": cid}, headers=_auth(normal))
    assert res.status_code == 200, res.text
    items = _notifications(client, owner)
    assert len(items) == 1
    assert items[0]["type"] == "follow"
    assert items[0]["ref_id"] == cid


def test_mention_creates_notification(ctx):
    """发帖 @ 提及 → 被提及者收到 mention 通知。"""
    client, owner, normal, cid, bid, owner_uid = (
        ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"], ctx["bid"], ctx["owner_uid"]
    )
    rich = [{"type": 1, "text": "看看这个 "}, {"type": 2, "at_user": {"id": owner_uid, "nick": "owner"}}]
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{bid}/posts",
        json={"title": "召唤帖", "rich_content": rich, "images": []},
        headers=_auth(normal),
    )
    assert res.status_code == 200, res.text
    items = _notifications(client, owner)
    assert len(items) == 1
    assert items[0]["type"] == "mention"


def test_join_review_creates_notification(ctx):
    """审核制频道：申请通过 → 申请人收到 review_result 通知。"""
    client, owner, normal = ctx["client"], ctx["owner"], ctx["normal"]
    cid = _create_community(client, owner, name="审核频道", join_setting=1)
    res = client.post(f"/api/v1/communities/{cid}/join", headers=_auth(normal))
    assert res.status_code == 200, res.text
    reqs = client.get(
        f"/api/v1/communities/{cid}/join-requests", headers=_auth(owner)
    ).json()["data"]["items"]
    assert len(reqs) == 1
    req_id = reqs[0]["id"]
    res = client.post(
        f"/api/v1/communities/{cid}/join-requests/{req_id}",
        json={"approve": True}, headers=_auth(owner),
    )
    assert res.status_code == 200, res.text
    items = _notifications(client, normal)
    assert len(items) == 1
    assert items[0]["type"] == "review_result"
    assert "通过" in items[0]["title"]


def test_shutup_creates_system_notification(ctx):
    """owner 禁言 normal → normal 收到 system 通知。"""
    client, owner, normal, cid, normal_uid = (
        ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"], ctx["normal_uid"]
    )
    res = client.post(
        f"/api/v1/communities/{cid}/members/{normal_uid}/shutup",
        json={"hours": 1}, headers=_auth(owner),
    )
    assert res.status_code == 200, res.text
    items = _notifications(client, normal)
    assert len(items) == 1
    assert items[0]["type"] == "system"
    assert "禁言" in items[0]["title"]


# ---------- 已读 / 未读数 ----------


def test_unread_count_and_mark_read(ctx):
    client, owner, normal, pid = ctx["client"], ctx["owner"], ctx["normal"], ctx["pid"]
    _comment(client, normal, pid, "a")
    _comment(client, normal, pid, "b")
    res = client.get("/api/v1/notifications/unread-count", headers=_auth(owner))
    assert res.json()["data"]["count"] == 2

    nid = _notifications(client, owner)[0]["id"]
    res = client.post(f"/api/v1/notifications/{nid}/read", headers=_auth(owner))
    assert res.status_code == 200, res.text
    assert client.get("/api/v1/notifications/unread-count", headers=_auth(owner)).json()["data"]["count"] == 1

    # 已读的排到后面
    items = _notifications(client, owner)
    assert items[0]["is_read"] is False
    assert items[1]["is_read"] is True

    # 不能读别人的通知
    res = client.post(f"/api/v1/notifications/{nid}/read", headers=_auth(normal))
    assert res.status_code == 404


def test_mark_all_read(ctx):
    client, owner, normal, pid = ctx["client"], ctx["owner"], ctx["normal"], ctx["pid"]
    _comment(client, normal, pid, "a")
    _comment(client, normal, pid, "b")
    res = client.post("/api/v1/notifications/read-all", headers=_auth(owner))
    assert res.json()["data"]["marked"] == 2
    assert client.get("/api/v1/notifications/unread-count", headers=_auth(owner)).json()["data"]["count"] == 0


# ---------- 通知开关 ----------


def test_settings_default_and_update(ctx):
    client, owner = ctx["client"], ctx["owner"]
    res = client.get("/api/v1/notifications/settings", headers=_auth(owner))
    assert res.status_code == 200, res.text
    settings = res.json()["data"]
    assert settings["comment"] is True

    res = client.put("/api/v1/notifications/settings", json={"comment": False}, headers=_auth(owner))
    assert res.status_code == 200, res.text
    assert res.json()["data"]["comment"] is False
    # 其他开关保持
    assert res.json()["data"]["mention"] is True


def test_settings_off_blocks_notification(ctx):
    """关掉 comment 开关后，评论不再生成通知。"""
    client, owner, normal, pid = ctx["client"], ctx["owner"], ctx["normal"], ctx["pid"]
    res = client.put("/api/v1/notifications/settings", json={"comment": False}, headers=_auth(owner))
    assert res.status_code == 200, res.text
    _comment(client, normal, pid, "关了开关")
    assert _notifications(client, owner) == []


def test_settings_unknown_key_rejected(ctx):
    client, owner = ctx["client"], ctx["owner"]
    res = client.put("/api/v1/notifications/settings", json={"foo": True}, headers=_auth(owner))
    assert res.status_code == 400
