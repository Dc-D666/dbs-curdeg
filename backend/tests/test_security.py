"""security 纯逻辑测试（不需要数据库）。"""
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify():
    hashed = hash_password("abc123")
    assert hashed != "abc123"
    assert verify_password("abc123", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("abc123", "not-a-hash")


def test_access_token_roundtrip():
    token = create_access_token(42)
    assert decode_token(token, "access") == 42
    # refresh token 不能当 access 用
    refresh = create_refresh_token(42)
    assert decode_token(refresh, "access") is None
    assert decode_token(refresh, "refresh") == 42


def test_token_type_mismatch():
    access = create_access_token(1)
    assert decode_token(access, "refresh") is None


def test_garbage_token():
    assert decode_token("garbage.token.value", "access") is None
