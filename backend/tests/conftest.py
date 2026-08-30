"""pytest 全局配置：独立测试库 + 事务回滚（快！）。

策略：
- CI（无 MySQL/Redis）只跑 test_smoke.py + test_security.py（纯逻辑），其余自动 skip；
- 本地集成测试：guild_test 库 **session 级建表一次**，每个测试外层事务 + savepoint 回滚。
"""
import os

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

# 必须在导入 app 之前设置：测试环境关闭后台任务（清理/统计/审核循环），
# 否则 while True 任务阻塞 TestClient 事件循环关闭导致 teardown 挂起
os.environ.setdefault("BACKGROUND_TASKS_ENABLED", "false")

from app.core.config import settings

# ---------- 数据库可用性检测 ----------
try:
    _probe = create_engine(settings.database_url, pool_pre_ping=True)
    with _probe.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    _probe.dispose()
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False


def pytest_collection_modifyitems(config, items):
    """无 DB 时，把除冒烟/纯逻辑外的测试全部 skip（CI 场景）。"""
    if DB_AVAILABLE:
        return
    smoke_or_logic = {"test_smoke.py", "test_security.py"}
    for item in items:
        fname = item.nodeid.split("::")[0].split("/")[-1]
        if fname not in smoke_or_logic:
            item.add_marker(pytest.mark.skip(reason="无 MySQL/Redis，跳过集成测试"))


# ---------- 测试库 URL ----------
def _base_engine():
    url = settings.database_url.split("?")[0]
    url = url.rsplit("/", 1)[0] + "/"
    return create_engine(url)


def _test_url() -> str:
    base, _, query = settings.database_url.partition("?")
    db = base.rsplit("/", 1)[1]
    new_db = "guild_test" if db == "guild_test" else f"{db}_test"
    new_base = base.rsplit("/", 1)[0] + "/" + new_db
    return f"{new_base}?{query}" if query else new_base


# ---------- 共享引擎（session 级，建表一次） ----------
@pytest.fixture(scope="session")
def test_engine():
    """guild_test 库 + 全部表（整个 session 建一次）。"""
    if not DB_AVAILABLE:
        pytest.skip("无 MySQL，跳过集成测试")
    base_engine = _base_engine()
    with base_engine.connect() as conn:
        conn.execute(text("CREATE DATABASE IF NOT EXISTS guild_test CHARACTER SET utf8mb4"))
        conn.commit()
    base_engine.dispose()

    engine = create_engine(_test_url(), pool_pre_ping=True)
    from app.db import Base
    import app.models  # noqa: F401

    # FK 护栏：模型变更后残留的旧外键可能让 drop_all 拓扑序失效（1217），
    # 关闭 FK 检查后按 metadata 顺序 drop/create，新建表仍带完整外键
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        conn.commit()
    try:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    finally:
        with engine.connect() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            conn.commit()
    yield engine
    engine.dispose()


# ---------- 事务回滚工具 ----------
def _make_session_factory(connection):
    """绑定到单连接的 session 工厂；commit 后自动重建 savepoint。"""
    Session = sessionmaker(bind=connection)

    @event.listens_for(Session, "after_transaction_end")
    def _renew_savepoint(session, transaction):
        # 事务结束后若 savepoint 已失效则重建（保持外层事务存活）
        if not connection.in_nested_transaction() and not transaction.nested:
            connection.begin_nested()

    return Session


@pytest.fixture()
def db_session(test_engine):
    """每个测试一个事务：外层 begin + savepoint，测试结束整体回滚。"""
    connection = test_engine.connect()
    transaction = connection.begin()
    connection.begin_nested()
    Session = _make_session_factory(connection)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(test_engine):
    """FastAPI TestClient：每个测试独立事务，请求结束后回滚。"""
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.db import get_db

    connection = test_engine.connect()
    transaction = connection.begin()
    connection.begin_nested()
    Session = _make_session_factory(connection)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client_ctx(test_engine):
    """client + 同一事务连接的 session（AI 审核测试用：API 发帖后可手动驱动审核任务）。

    与 client 不同：这里把 session 暴露给测试，审核任务处理（process_review_task /
    appeal）与请求共享同一连接，数据互相可见；测试结束整体回滚。
    """
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.db import get_db

    connection = test_engine.connect()
    transaction = connection.begin()
    connection.begin_nested()
    Session = _make_session_factory(connection)
    session = Session()

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as c:
        yield c, session
    fastapi_app.dependency_overrides.clear()
    transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def _mock_llm_gateway(monkeypatch):
    """全局 mock LLM 网关（阶段 6）：测试绝不真实调用外部 AI API。

    - chat：审核 prompt → 通过；复审 → 通过；其余 → 固定文本
    - stream：固定两个文本块
    - embed：确定性伪向量（同文本同向量，便于相似度断言）
    同时关闭发帖自动入队（审核流程由测试手动调用 process_review_task 驱动）。
    """
    from app.ai import llm_gateway
    from app.core.config import settings

    def fake_chat(messages, model="", max_tokens=1024, temperature=0.7, feature="chat", user_id=None):
        text = " ".join(str(m.get("content", "")) for m in messages)
        if "内容审核员" in text:
            return '{"pass": true, "type": "", "detail": ""}'
        if "复审员" in text:
            return '{"decision": "pass", "detail": "测试复审通过"}'
        return "这是 AI 生成的测试回复。"

    def fake_stream(messages, model="", max_tokens=2048, temperature=0.7, feature="chat"):
        return iter(["AI 生成", " 的测试", "内容"])

    def fake_embed(text, feature="embed", user_id=None):
        # 确定性伪向量：基于文本哈希
        import hashlib

        h = hashlib.md5(text.encode("utf-8")).digest()
        return [1.0 if (b % 3 == 0) else 0.0 for b in h]

    monkeypatch.setattr(llm_gateway, "chat", fake_chat)
    monkeypatch.setattr(llm_gateway, "stream", fake_stream)
    monkeypatch.setattr(llm_gateway, "embed", fake_embed)
    monkeypatch.setattr(settings, "AI_REVIEW_ENABLED", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)  # 共享 Redis，避免限流串扰
