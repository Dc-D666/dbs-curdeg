"""阶段3 API 测试：发帖/帖子流/评论楼中楼/点赞幂等/关注（测试库 guild_test）。

覆盖 4 类核心验收：发帖权限（版块 allow_post_role_ids）、评论嵌套（一层）、
点赞幂等（唯一约束不重复计数）、Feed 排序（置顶恒顶）。
"""
import redis
import pytest

from app.core.config import settings
from app.services.email_service import CODE_PREFIX


def _seed_code(email: str, code: str = "123456"):
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    r.setex(f"{CODE_PREFIX}{email}", 300, code)


def _register(client, username: str, email: str, password: str = "pass123"):
    _seed_code(email)
    res = client.post("/api/v1/auth/register", json={
        "username": username, "email": email, "code": "123456", "password": password,
    })
    assert res.status_code == 200, res.text
    return res.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_community(client, token: str, name: str = "内容测试频道", join_setting: int = 0) -> int:
    res = client.post("/api/v1/communities", json={"name": name, "join_setting": join_setting}, headers=_auth(token))
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


def _create_board(client, token: str, cid: int, name: str = "闲聊", allow_post_role_ids: list | None = None) -> int:
    body = {"name": name, "description": "测试版块"}
    if allow_post_role_ids is not None:
        body["allow_post_role_ids"] = allow_post_role_ids
    res = client.post(f"/api/v1/communities/{cid}/boards", json=body, headers=_auth(token))
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


def _create_post(client, token: str, cid: int, bid: int, title: str = "测试帖子", content: str = "帖子内容") -> int:
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{bid}/posts",
        json={"title": title, "content": content, "images": []},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


@pytest.fixture()
def ctx(client):
    """owner + normal（已加入频道）+ 版块。"""
    owner = _register(client, "postowner", "postowner@test.com")
    normal = _register(client, "postnormal", "postnormal@test.com")
    cid = _create_community(client, owner)
    bid = _create_board(client, owner, cid)
    res = client.post(f"/api/v1/communities/{cid}/join", headers=_auth(normal))
    assert res.status_code == 200, res.text
    return {"client": client, "owner": owner, "normal": normal, "cid": cid, "bid": bid}


# ---------- 发帖权限 ----------


def test_create_post_requires_member(ctx):
    """非成员发帖 403。"""
    client, cid, bid = ctx["client"], ctx["cid"], ctx["bid"]
    outsider = _register(client, "postoutsider", "postoutsider@test.com")
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{bid}/posts",
        json={"title": "t", "content": "c"},
        headers=_auth(outsider),
    )
    assert res.status_code == 403


def test_board_post_role_restriction(ctx):
    """版块发帖白名单非空时，未命中身份组的成员不能发帖；owner 放行。

    08-29 外键化：白名单存 board_role_perms 关系表，悬空角色 ID 会被 FK 拒绝，
    故先创建真实身份组再引用。
    """
    client, owner, normal, cid = ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"]
    # 创建真实身份组，白名单仅允许它发帖
    role_res = client.post(f"/api/v1/communities/{cid}/roles", json={"name": "贵宾"}, headers=_auth(owner))
    assert role_res.status_code == 200
    vip_role_id = role_res.json()["data"]["id"]
    restricted_bid = _create_board(client, owner, cid, name="受限版块", allow_post_role_ids=[vip_role_id])
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{restricted_bid}/posts",
        json={"title": "t", "content": "c"},
        headers=_auth(normal),
    )
    assert res.status_code == 403
    # owner 不受限
    res2 = client.post(
        f"/api/v1/communities/{cid}/boards/{restricted_bid}/posts",
        json={"title": "t2", "content": "c2"},
        headers=_auth(owner),
    )
    assert res2.status_code == 200


def test_create_post_and_feed(ctx):
    """发帖成功，latest/hot feed 都能看到。"""
    client, owner, cid, bid = ctx["client"], ctx["owner"], ctx["cid"], ctx["bid"]
    pid = _create_post(client, owner, cid, bid)
    for sort in ("latest", "hot"):
        res = client.get(f"/api/v1/communities/{cid}/feed", params={"sort": sort})
        assert res.status_code == 200
        items = res.json()["data"]["items"]
        assert any(p["id"] == pid for p in items)
    # 详情含互动状态与作者信息
    detail = client.get(f"/api/v1/posts/{pid}").json()["data"]
    assert detail["author_nickname"]
    assert detail["community_name"] == "内容测试频道"
    assert detail["board_name"] == "闲聊"


# ---------- 编辑/删除/置顶权限 ----------


def test_update_delete_post_permissions(ctx):
    client, owner, normal, cid, bid = ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"], ctx["bid"]
    pid = _create_post(client, owner, cid, bid)
    # 他人编辑 403
    res = client.put(f"/api/v1/posts/{pid}", json={"title": "hack"}, headers=_auth(normal))
    assert res.status_code == 403
    # 本人编辑成功
    res = client.put(f"/api/v1/posts/{pid}", json={"title": "改标题"}, headers=_auth(owner))
    assert res.status_code == 200
    assert res.json()["data"]["title"] == "改标题"
    # 他人删除 403（normal 非 owner/admin）
    res = client.delete(f"/api/v1/posts/{pid}", headers=_auth(normal))
    assert res.status_code == 403
    # owner 删除成功 → 详情 404
    res = client.delete(f"/api/v1/posts/{pid}", headers=_auth(owner))
    assert res.status_code == 200
    assert client.get(f"/api/v1/posts/{pid}").status_code == 404


def test_top_stays_first_in_feed(ctx):
    """置顶恒顶：后发的置顶帖仍排在最前。"""
    client, owner, cid, bid = ctx["client"], ctx["owner"], ctx["cid"], ctx["bid"]
    _create_post(client, owner, cid, bid, title="普通1")
    top_pid = _create_post(client, owner, cid, bid, title="置顶帖")
    _create_post(client, owner, cid, bid, title="普通2")
    # 普通成员不能置顶
    res = client.post(f"/api/v1/posts/{top_pid}/top", headers=_auth(ctx["normal"]))
    assert res.status_code == 403
    # owner 置顶
    res = client.post(f"/api/v1/posts/{top_pid}/top", headers=_auth(owner))
    assert res.status_code == 200
    items = client.get(f"/api/v1/communities/{cid}/feed", params={"sort": "latest"}).json()["data"]["items"]
    assert items[0]["id"] == top_pid
    assert items[0]["is_top"] is True
    # 精华标记
    res = client.post(f"/api/v1/posts/{top_pid}/essence", headers=_auth(owner))
    assert res.status_code == 200
    detail = client.get(f"/api/v1/posts/{top_pid}").json()["data"]
    assert detail["is_essence"] is True


# ---------- 评论（楼中楼一层） ----------


def test_comment_flow_and_nesting_limit(ctx):
    client, owner, normal, cid, bid = ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"], ctx["bid"]
    pid = _create_post(client, owner, cid, bid)
    # 顶层评论
    res = client.post(f"/api/v1/posts/{pid}/comments", json={"content": "一楼"}, headers=_auth(normal))
    assert res.status_code == 200
    cid1 = res.json()["data"]["id"]
    # 楼中楼回复（回复接口自动带 parent_id）
    res = client.post(f"/api/v1/comments/{cid1}/replies", json={"content": "回复一楼"}, headers=_auth(owner))
    assert res.status_code == 200
    reply = res.json()["data"]
    assert reply["parent_id"] == cid1
    assert reply["reply_to_nickname"]  # 自动指向被回复评论作者
    # 二层嵌套拒绝
    res = client.post(f"/api/v1/comments/{reply['id']}/replies", json={"content": "三层"}, headers=_auth(normal))
    assert res.status_code == 400
    # 评论列表计数
    lst = client.get(f"/api/v1/posts/{pid}/comments").json()["data"]
    assert lst["total"] == 1  # 顶层只有一条
    replies = client.get(f"/api/v1/comments/{cid1}/replies").json()["data"]
    assert replies["total"] == 1
    # 帖子 comment_count 更新
    assert client.get(f"/api/v1/posts/{pid}").json()["data"]["comment_count"] == 2


def test_comment_delete_permission(ctx):
    client, owner, normal, cid, bid = ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"], ctx["bid"]
    pid = _create_post(client, owner, cid, bid)
    res = client.post(f"/api/v1/posts/{pid}/comments", json={"content": "评论"}, headers=_auth(normal))
    comment_id = res.json()["data"]["id"]
    # 他人（owner 之外的作者？owner 是 moderator 可删）——用第三个用户删他人评论
    other = _register(client, "commentother", "commentother@test.com")
    client.post(f"/api/v1/communities/{cid}/join", headers=_auth(other))
    res = client.delete(f"/api/v1/comments/{comment_id}", headers=_auth(other))
    assert res.status_code == 403
    # 作者本人删除成功
    res = client.delete(f"/api/v1/comments/{comment_id}", headers=_auth(normal))
    assert res.status_code == 200
    # owner 作为版主可删：再建一条由 owner 删
    res = client.post(f"/api/v1/posts/{pid}/comments", json={"content": "被版主删"}, headers=_auth(normal))
    cid2 = res.json()["data"]["id"]
    res = client.delete(f"/api/v1/comments/{cid2}", headers=_auth(owner))
    assert res.status_code == 200


# ---------- 点赞幂等 ----------


def test_like_idempotent(ctx):
    """重复点赞不重复计数；取消后重新点赞计数恢复。"""
    client, owner, normal, cid, bid = ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"], ctx["bid"]
    pid = _create_post(client, owner, cid, bid)
    # 第一次点赞 → count=1
    res = client.post("/api/v1/likes", json={"post_id": pid}, headers=_auth(normal))
    assert res.status_code == 200
    assert res.json()["data"]["count"] == 1
    # 重复点赞 → 幂等，count 仍为 1
    res = client.post("/api/v1/likes", json={"post_id": pid}, headers=_auth(normal))
    assert res.json()["data"]["count"] == 1
    detail = client.get(f"/api/v1/posts/{pid}", headers=_auth(normal)).json()["data"]
    assert detail["like_count"] == 1
    assert detail["is_liked"] is True
    # 取消 → 0
    res = client.delete("/api/v1/likes", params={"post_id": pid}, headers=_auth(normal))
    assert res.json()["data"]["count"] == 0
    # 再点 → 1
    client.post("/api/v1/likes", json={"post_id": pid}, headers=_auth(normal))
    assert client.get(f"/api/v1/posts/{pid}").json()["data"]["like_count"] == 1
    # 参数二选一校验
    res = client.post("/api/v1/likes", json={}, headers=_auth(normal))
    assert res.status_code == 400
    # 评论点赞
    res = client.post(f"/api/v1/posts/{pid}/comments", json={"content": "被赞的评论"}, headers=_auth(normal))
    comment_id = res.json()["data"]["id"]
    res = client.post("/api/v1/likes", json={"comment_id": comment_id}, headers=_auth(owner))
    assert res.status_code == 200
    assert res.json()["data"]["count"] == 1


# ---------- 关注与关注流 ----------


def test_follow_and_my_feed(ctx):
    client, owner, normal, cid, bid = ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"], ctx["bid"]
    _create_post(client, owner, cid, bid, title="关注流帖子")
    # 未关注时 /me/feed 为空
    feed = client.get("/api/v1/me/feed", headers=_auth(normal)).json()["data"]
    assert feed["items"] == []
    # 关注（幂等）
    res = client.post("/api/v1/follows", json={"community_id": cid}, headers=_auth(normal))
    assert res.status_code == 200
    res = client.post("/api/v1/follows", json={"community_id": cid}, headers=_auth(normal))
    assert res.status_code == 200
    # 关注流可见该频道帖子
    feed = client.get("/api/v1/me/feed", headers=_auth(normal)).json()["data"]
    assert any(p["title"] == "关注流帖子" for p in feed["items"])
    # 详情 is_followed 标记
    pid = client.get(f"/api/v1/communities/{cid}/feed").json()["data"]["items"][0]["id"]
    detail = client.get(f"/api/v1/posts/{pid}", headers=_auth(normal)).json()["data"]
    assert detail["is_followed"] is True
    # 取消关注 → 流清空
    res = client.delete("/api/v1/follows", params={"community_id": cid}, headers=_auth(normal))
    assert res.status_code == 200
    feed = client.get("/api/v1/me/feed", headers=_auth(normal)).json()["data"]
    assert feed["items"] == []


# ---------- 审查修复回归：频道状态/权限边界 ----------


def test_closed_community_blocks_writes(ctx):
    """关闭频道后，评论/回复/点赞/编辑/置顶全部拒绝（写路径统一校验频道状态）。"""
    client, owner, normal, cid, bid = ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"], ctx["bid"]
    pid = _create_post(client, owner, cid, bid)
    cid1 = client.post(f"/api/v1/posts/{pid}/comments", json={"content": "评论"}, headers=_auth(normal)).json()["data"]["id"]
    # owner 关闭频道
    res = client.put(f"/api/v1/communities/{cid}/status", json={"status": 1}, headers=_auth(owner))
    assert res.status_code == 200
    # 评论 → 404（频道不存在口径）
    assert client.post(f"/api/v1/posts/{pid}/comments", json={"content": "x"}, headers=_auth(normal)).status_code == 404
    assert client.post(f"/api/v1/comments/{cid1}/replies", json={"content": "x"}, headers=_auth(normal)).status_code == 404
    # 点赞/取消 → 404
    assert client.post("/api/v1/likes", json={"post_id": pid}, headers=_auth(normal)).status_code == 404
    assert client.delete("/api/v1/likes", params={"post_id": pid}, headers=_auth(normal)).status_code == 404
    # 编辑/置顶/精华/删除 → 404
    assert client.put(f"/api/v1/posts/{pid}", json={"title": "x"}, headers=_auth(owner)).status_code == 404
    assert client.post(f"/api/v1/posts/{pid}/top", headers=_auth(owner)).status_code == 404
    assert client.post(f"/api/v1/posts/{pid}/essence", headers=_auth(owner)).status_code == 404
    assert client.delete(f"/api/v1/posts/{pid}", headers=_auth(owner)).status_code == 404
    # 发帖 → 404
    assert client.post(f"/api/v1/communities/{cid}/boards/{bid}/posts",
                       json={"title": "t", "content": "c"}, headers=_auth(owner)).status_code == 404


def test_like_requires_member(ctx):
    """非成员不能点赞/取消点赞。"""
    client, owner, cid, bid = ctx["client"], ctx["owner"], ctx["cid"], ctx["bid"]
    pid = _create_post(client, owner, cid, bid)
    outsider = _register(client, "likeoutsider", "likeoutsider@test.com")
    assert client.post("/api/v1/likes", json={"post_id": pid}, headers=_auth(outsider)).status_code == 403
    assert client.delete("/api/v1/likes", params={"post_id": pid}, headers=_auth(outsider)).status_code == 403


def test_reply_to_deleted_post_rejected(ctx):
    """帖子软删后，其评论不可再回复。"""
    client, owner, cid, bid = ctx["client"], ctx["owner"], ctx["cid"], ctx["bid"]
    pid = _create_post(client, owner, cid, bid)
    cid1 = client.post(f"/api/v1/posts/{pid}/comments", json={"content": "评论"}, headers=_auth(owner)).json()["data"]["id"]
    assert client.delete(f"/api/v1/posts/{pid}", headers=_auth(owner)).status_code == 200
    assert client.post(f"/api/v1/comments/{cid1}/replies", json={"content": "x"}, headers=_auth(owner)).status_code == 404


def test_delete_top_comment_cascades_replies(ctx):
    """删顶层评论级联软删楼中楼回复，comment_count 同步扣减。"""
    client, owner, normal, cid, bid = ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"], ctx["bid"]
    pid = _create_post(client, owner, cid, bid)
    cid1 = client.post(f"/api/v1/posts/{pid}/comments", json={"content": "顶层"}, headers=_auth(normal)).json()["data"]["id"]
    client.post(f"/api/v1/comments/{cid1}/replies", json={"content": "回复1"}, headers=_auth(owner))
    client.post(f"/api/v1/comments/{cid1}/replies", json={"content": "回复2"}, headers=_auth(owner))
    assert client.get(f"/api/v1/posts/{pid}").json()["data"]["comment_count"] == 3
    # 删顶层 → 级联
    assert client.delete(f"/api/v1/comments/{cid1}", headers=_auth(normal)).status_code == 200
    detail = client.get(f"/api/v1/posts/{pid}").json()["data"]
    assert detail["comment_count"] == 0
    # 回复列表不可见（父评论已删 → 404）
    assert client.get(f"/api/v1/comments/{cid1}/replies").status_code == 404
    # 评论列表为空
    assert client.get(f"/api/v1/posts/{pid}/comments").json()["data"]["total"] == 0


def test_feed_board_filter(ctx):
    """feed 按版块过滤：只返回指定版块的帖子。"""
    client, owner, cid, bid = ctx["client"], ctx["owner"], ctx["cid"], ctx["bid"]
    bid2 = _create_board(client, owner, cid, name="第二个版块")
    pid1 = _create_post(client, owner, cid, bid, title="版块一帖子")
    pid2 = _create_post(client, owner, cid, bid2, title="版块二帖子")
    items1 = client.get(f"/api/v1/communities/{cid}/feed", params={"board_id": bid}).json()["data"]["items"]
    items2 = client.get(f"/api/v1/communities/{cid}/feed", params={"board_id": bid2}).json()["data"]["items"]
    assert all(p["id"] == pid1 for p in items1)
    assert all(p["id"] == pid2 for p in items2)


def test_post_rich_content_segments(ctx):
    """富文本分片发帖：rich_content 原样存储，source_markdown 提取纯文本（含链接显示文字）。"""
    client, owner, cid, bid = ctx["client"], ctx["owner"], ctx["cid"], ctx["bid"]
    rich = [
        {"type": 1, "text": "第一段文本"},
        {"type": 3, "url": "https://example.com/doc", "display_text": "参考文档", "url_type": 10},
        {"type": 1, "text": "第二段"},
    ]
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{bid}/posts",
        json={"title": "分片帖", "rich_content": rich, "images": []},
        headers=_auth(owner),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["rich_content"] == rich  # 原样返回（4.4 契约）
    assert data["source_markdown"] == "第一段文本参考文档第二段"  # 纯文本提取
    # 编辑时 rich_content 可替换
    rich2 = [{"type": 1, "text": "改后的内容"}]
    res = client.put(f"/api/v1/posts/{data['id']}", json={"rich_content": rich2}, headers=_auth(owner))
    assert res.status_code == 200
    assert res.json()["data"]["source_markdown"] == "改后的内容"
    # 二者都不提供 → 400
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{bid}/posts",
        json={"title": "空内容帖"},
        headers=_auth(owner),
    )
    assert res.status_code == 400


def test_at_mention_requires_member(ctx):
    """@提及分片：目标必须是频道成员；非成员被拒。"""
    client, owner, normal, cid, bid = ctx["client"], ctx["owner"], ctx["normal"], ctx["cid"], ctx["bid"]
    # 成员 id（normal 已加入，owner 是频道主）
    me = client.get("/api/v1/users/me", headers=_auth(owner)).json()["data"]["id"]
    other = _register(client, "atoutsider", "atoutsider@test.com")
    outsider_id = client.get("/api/v1/users/me", headers=_auth(other)).json()["data"]["id"]
    rich = [{"type": 1, "text": "你好 "}, {"type": 2, "at_user": {"id": me, "nick": "频道主"}}]
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{bid}/posts",
        json={"title": "@帖", "rich_content": rich, "images": []},
        headers=_auth(owner),
    )
    assert res.status_code == 200
    assert "频道主" in res.json()["data"]["source_markdown"]  # 纯文本含 @昵称
    # 提及非成员 → 400
    rich_bad = [{"type": 2, "at_user": {"id": outsider_id, "nick": "外人"}}]
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{bid}/posts",
        json={"title": "越权@", "rich_content": rich_bad, "images": []},
        headers=_auth(owner),
    )
    assert res.status_code == 400
    assert "成员" in res.json()["message"]


def test_topic_upsert_and_extract(ctx):
    """话题：创建/upsert 幂等；分片纯文本提取 #话题名。"""
    client, owner, cid, bid = ctx["client"], ctx["owner"], ctx["cid"], ctx["bid"]
    res = client.post(f"/api/v1/communities/{cid}/topics", json={"name": "日常"}, headers=_auth(owner))
    assert res.status_code == 200
    tid = res.json()["data"]["id"]
    # 同名 upsert 返回同一话题
    res2 = client.post(f"/api/v1/communities/{cid}/topics", json={"name": "日常"}, headers=_auth(owner))
    assert res2.json()["data"]["id"] == tid
    # 列表
    lst = client.get(f"/api/v1/communities/{cid}/topics").json()["data"]
    assert any(t["name"] == "日常" for t in lst)
    # 分片引用话题 → source_markdown 含 #日常
    rich = [{"type": 8, "topic": {"topic_id": tid, "topic_name": "日常"}}, {"type": 1, "text": "今天聊点啥"}]
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{bid}/posts",
        json={"title": "话题帖", "rich_content": rich, "images": []},
        headers=_auth(owner),
    )
    assert res.status_code == 200
    assert res.json()["data"]["source_markdown"] == "#日常今天聊点啥"
    # 非成员不能建话题
    outsider = _register(client, "topicoutsider", "topicoutsider@test.com")
    res = client.post(f"/api/v1/communities/{cid}/topics", json={"name": "越权"}, headers=_auth(outsider))
    assert res.status_code == 403


def test_style_segments_extract(ctx):
    """样式分片（bold/color）存储与纯文本提取。"""
    client, owner, cid, bid = ctx["client"], ctx["owner"], ctx["cid"], ctx["bid"]
    rich = [
        {"type": 1, "text": "重点", "style": {"bold": True, "color": "#d54941"}},
        {"type": 4, "emoji": {"id": "1", "char": "🔥"}},
    ]
    res = client.post(
        f"/api/v1/communities/{cid}/boards/{bid}/posts",
        json={"title": "样式帖", "rich_content": rich, "images": []},
        headers=_auth(owner),
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["rich_content"][0]["style"]["bold"] is True
    assert data["source_markdown"] == "重点🔥"


def test_global_feed(ctx):
    """全站帖子流：latest/hot 都能看到新发帖子（首页用）。"""
    client, owner, cid, bid = ctx["client"], ctx["owner"], ctx["cid"], ctx["bid"]
    pid = _create_post(client, owner, cid, bid, title="全站可见帖")
    for sort in ("latest", "hot"):
        res = client.get("/api/v1/feed", params={"sort": sort})
        assert res.status_code == 200
        items = res.json()["data"]["items"]
        assert any(p["id"] == pid for p in items)
        # 全站流带频道名（首页展示）
        assert all(p["community_name"] for p in items)
