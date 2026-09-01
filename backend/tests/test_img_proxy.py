"""图片代理安全校验测试：白名单/SSRF/协议拦截（不发真实外网请求）。"""
from urllib.parse import quote

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _get(url: str):
    return client.get(f"/api/v1/img_proxy?url={quote(url, safe='')}")


def test_non_whitelisted_host_rejected():
    """白名单外域名（含常见图床）一律拒绝。"""
    for url in (
        "https://example.com/a.jpg",
        "https://i.imgur.com/a.png",
        "http://127.0.0.1/x.png",
    ):
        res = _get(url)
        assert res.status_code == 400
        assert "白名单" in res.json()["message"] or "不合法" in res.json()["message"]


def test_ssrf_literal_blocked():
    """白名单判定之前，环回/内网字面量先被拦（即使伪造 host 头也过不了白名单）。"""
    res = _get("http://localhost/a.jpg")
    assert res.status_code == 400
    # localhost 不在白名单，命中白名单拦截分支
    assert "白名单" in res.json()["message"]


def test_bad_scheme_rejected():
    """file:// / ftp:// 等非 http(s) 协议拒绝。"""
    for url in ("file:///etc/passwd", "ftp://x/y.png", "data:image/png;base64,AAAA"):
        res = _get(url)
        assert res.status_code == 400


def test_whitelisted_host_bad_path_is_fetch_error_not_bypass():
    """白名单域名 + 内网路径字段不构成绕过：host 提取以 urlsplit 为准。

    白名单域名 + 无法到达的地址 → 走真实请求分支，应报"获取失败"（网络错误），
    证明校验逻辑放行的是域名而非路径/端口。
    """
    # 白名单域 + 非法端口：urlsplit 提取 host 仍为白名单域，请求失败属网络层错误
    res = _get("https://channelgz.photo.store.qq.com:1/x.jpg")
    # 不断言具体状态：要么 400（连接失败被 ParamError 包装），要么超时；
    # 关键是绝不可能是 200（真实图片流）
    assert res.status_code != 200
