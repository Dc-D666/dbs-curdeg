"""pytest 全局配置：独立测试库 + 事务回滚（快！）。

策略：
- CI（无 MySQL/Redis）只跑 test_smoke.py + test_security.py（纯逻辑），其余自动 skip；
- 本地集成测试：guild_test 库 **session 级建表一次**，每个测试外层事务 + savepoint 回滚。
"""
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

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

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
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
