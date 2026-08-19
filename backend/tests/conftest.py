"""pytest 全局配置：使用独立测试库（避免污染生产/开发库）。

策略：基于 settings.database_url 派生 guild_test 库；
若测试库不存在则创建；每个测试函数结束回滚（嵌套事务 + savepoint）。
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _base_engine():
    # 连到 MySQL 实例（不指定库）用于建库：去掉路径与 query 部分
    url = settings.database_url.split("?")[0]
    url = url.rsplit("/", 1)[0] + "/"
    return create_engine(url)


def _test_url() -> str:
    """派生测试库 URL：guild -> guild_test（保留 charset 参数）。"""
    base, _, query = settings.database_url.partition("?")
    db = base.rsplit("/", 1)[1]
    if db == "guild_test":
        new_db = db
    else:
        new_db = f"{db}_test"
    new_base = base.rsplit("/", 1)[0] + "/" + new_db
    return f"{new_base}?{query}" if query else new_base


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """确保 guild_test 测试库存在（幂等）。"""
    engine = _base_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE DATABASE IF NOT EXISTS guild_test CHARACTER SET utf8mb4"))
        conn.commit()
    yield
    engine.dispose()


@pytest.fixture()
def db_session():
    """每个测试一个事务回滚的会话（真实测试库）。"""
    test_url = _test_url()
    engine = create_engine(test_url, pool_pre_ping=True)
    # 建表（从 models 元数据）
    from app.db import Base
    import app.models  # noqa: F401

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client():
    """FastAPI TestClient（依赖覆盖：db_session 由测试驱动）。"""
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.db import get_db

    test_url = _test_url()
    engine = create_engine(test_url, pool_pre_ping=True)

    from app.db import Base
    import app.models  # noqa: F401

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

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
    engine.dispose()
