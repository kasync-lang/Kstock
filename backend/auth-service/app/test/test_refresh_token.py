from __future__ import annotations

import json
from datetime import timedelta
import pytest
from beanie import PydanticObjectId

from app.api import login
from app.core import security, session as session_manager
from app.core.config import settings


@pytest.mark.asyncio
async def test_login_sets_refresh_cookie_and_stores_hash_in_redis(
    client, user_account, in_memory_redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_authenticate(*, email: str, password: str):
        return user_account

    monkeypatch.setattr(login.crud, "authenticate", fake_authenticate)
    monkeypatch.setattr(
        login.security,
        "create_access_token",
        lambda subject, expires_delta: "access-token-123",
    )

    response = client.post(
        "/login/access-token",
        data={"username": user_account.email, "password": "StrongPass1!"},
    )

    assert response.status_code == 200
    assert response.json() == {"access_token": "access-token-123", "token_type": "Bearer"}

    # HttpOnly Cookie set
    cookies = response.cookies
    assert settings.REFRESH_TOKEN_COOKIE_NAME in cookies
    raw_refresh_token = cookies[settings.REFRESH_TOKEN_COOKIE_NAME]

    set_cookie_header = response.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie_header
    assert f"Path={settings.REFRESH_TOKEN_COOKIE_PATH}" in set_cookie_header

    # Verify Redis stores ONLY the hash of the token, NEVER the plain text token
    assert raw_refresh_token not in in_memory_redis.store
    token_hash = session_manager.hash_refresh_token(raw_refresh_token)
    assert f"refresh_token:{token_hash}" in in_memory_redis.store

    token_data = json.loads(in_memory_redis.store[f"refresh_token:{token_hash}"])
    assert token_data["status"] == "active"
    assert token_data["user_id"] == str(user_account.id)

    session_id = token_data["session_id"]
    assert f"session:{session_id}" in in_memory_redis.store
    session_data = json.loads(in_memory_redis.store[f"session:{session_id}"])
    assert session_data["revoked"] is False
    assert session_data["current_token_hash"] == token_hash
    assert session_data["user_id"] == str(user_account.id)


@pytest.mark.asyncio
async def test_refresh_token_rotation_success(
    client, user_account, in_memory_redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 1. Create initial session in Redis
    session_id, initial_token = await session_manager.create_refresh_session(
        redis=in_memory_redis,
        user_id=str(user_account.id),
    )
    initial_hash = session_manager.hash_refresh_token(initial_token)

    monkeypatch.setattr(
        login.User,
        "get",
        staticmethod(lambda account_id: _awaitable(user_account)),
    )
    monkeypatch.setattr(
        login.Oauth2Account,
        "get",
        staticmethod(lambda account_id: _awaitable(None)),
    )

    # 2. Call /auth/refresh with initial token in cookie
    client.cookies.clear()
    client.cookies.set(settings.REFRESH_TOKEN_COOKIE_NAME, initial_token)
    response = client.post("/auth/refresh")

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "Bearer"

    # 3. Verify new rotated token was set in cookie
    new_token = response.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    assert new_token is not None
    assert new_token != initial_token

    new_hash = session_manager.hash_refresh_token(new_token)

    # 4. Verify Redis state
    # Old token is marked as rotated
    old_record = json.loads(in_memory_redis.store[f"refresh_token:{initial_hash}"])
    assert old_record["status"] == "rotated"
    assert old_record["rotated_at"] is not None

    # New token is active
    new_record = json.loads(in_memory_redis.store[f"refresh_token:{new_hash}"])
    assert new_record["status"] == "active"
    assert new_record["session_id"] == session_id

    # Session updated to point to new hash
    session_record = json.loads(in_memory_redis.store[f"session:{session_id}"])
    assert session_record["current_token_hash"] == new_hash
    assert session_record["revoked"] is False


@pytest.mark.asyncio
async def test_refresh_token_reuse_detection_revokes_session(
    client, user_account, in_memory_redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, token_v1 = await session_manager.create_refresh_session(
        redis=in_memory_redis,
        user_id=str(user_account.id),
    )
    monkeypatch.setattr(
        login.User,
        "get",
        staticmethod(lambda account_id: _awaitable(user_account)),
    )
    monkeypatch.setattr(
        login.Oauth2Account,
        "get",
        staticmethod(lambda account_id: _awaitable(None)),
    )

    # Legitimate rotation: v1 -> v2
    client.cookies.clear()
    client.cookies.set(settings.REFRESH_TOKEN_COOKIE_NAME, token_v1)
    res1 = client.post("/auth/refresh")
    assert res1.status_code == 200
    token_v2 = res1.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    assert token_v2 != token_v1

    # ATTACK / REUSE: Attacker attempts to use token_v1 again!
    client.cookies.clear()
    client.cookies.set(settings.REFRESH_TOKEN_COOKIE_NAME, token_v1)
    res_attack = client.post("/auth/refresh")

    # Reuse is detected, immediate 401 and session revoked
    assert res_attack.status_code == 401
    assert "reuse detected" in res_attack.json()["detail"].lower()

    # Cookie is cleared on client
    set_cookie_header = res_attack.headers.get("set-cookie", "")
    assert "Max-Age=0" in set_cookie_header or 'refresh_token=""' in set_cookie_header

    # Session in Redis is revoked
    session_record = json.loads(in_memory_redis.store[f"session:{session_id}"])
    assert session_record["revoked"] is True

    # Active token v2 was deleted/invalidated
    hash_v2 = session_manager.hash_refresh_token(token_v2)
    assert f"refresh_token:{hash_v2}" not in in_memory_redis.store

    # Subsequent attempt to use token_v2 ALSO fails
    client.cookies.clear()
    client.cookies.set(settings.REFRESH_TOKEN_COOKIE_NAME, token_v2)
    res_v2 = client.post("/auth/refresh")
    assert res_v2.status_code == 401


@pytest.mark.asyncio
async def test_refresh_missing_cookie_rejected(client) -> None:
    client.cookies.clear()
    response = client.post("/auth/refresh")

    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token missing"


@pytest.mark.asyncio
async def test_refresh_unknown_token_rejected(client) -> None:
    client.cookies.clear()
    client.cookies.set(settings.REFRESH_TOKEN_COOKIE_NAME, "unknown-opaque-token")
    response = client.post("/auth/refresh")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired refresh token"
    # Cookie cleared
    set_cookie = response.headers.get("set-cookie", "")
    assert "Max-Age=0" in set_cookie or 'refresh_token=""' in set_cookie


@pytest.mark.asyncio
async def test_refresh_revoked_session_rejected(
    client, user_account, in_memory_redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, token = await session_manager.create_refresh_session(
        redis=in_memory_redis,
        user_id=str(user_account.id),
    )
    # Revoke session explicitly
    await session_manager.revoke_session(in_memory_redis, session_id)

    client.cookies.clear()
    client.cookies.set(settings.REFRESH_TOKEN_COOKIE_NAME, token)
    response = client.post("/auth/refresh")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_inactive_user_revokes_session(
    client, inactive_user_account, in_memory_redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, token = await session_manager.create_refresh_session(
        redis=in_memory_redis,
        user_id=str(inactive_user_account.id),
    )
    monkeypatch.setattr(
        login.User,
        "get",
        staticmethod(lambda account_id: _awaitable(inactive_user_account)),
    )
    monkeypatch.setattr(
        login.Oauth2Account,
        "get",
        staticmethod(lambda account_id: _awaitable(None)),
    )

    client.cookies.clear()
    client.cookies.set(settings.REFRESH_TOKEN_COOKIE_NAME, token)
    response = client.post("/auth/refresh")

    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"

    # Session was revoked
    session_record = json.loads(in_memory_redis.store[f"session:{session_id}"])
    assert session_record["revoked"] is True


@pytest.mark.asyncio
async def test_refresh_user_not_found_revokes_session(
    client, in_memory_redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_user_id = str(PydanticObjectId())
    session_id, token = await session_manager.create_refresh_session(
        redis=in_memory_redis,
        user_id=fake_user_id,
    )
    monkeypatch.setattr(
        login.User,
        "get",
        staticmethod(lambda account_id: _awaitable(None)),
    )
    monkeypatch.setattr(
        login.Oauth2Account,
        "get",
        staticmethod(lambda account_id: _awaitable(None)),
    )

    client.cookies.clear()
    client.cookies.set(settings.REFRESH_TOKEN_COOKIE_NAME, token)
    response = client.post("/auth/refresh")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

    session_record = json.loads(in_memory_redis.store[f"session:{session_id}"])
    assert session_record["revoked"] is True


@pytest.mark.asyncio
async def test_logout_revokes_session_and_clears_cookie(
    client, user_account, in_memory_redis
) -> None:
    session_id, token = await session_manager.create_refresh_session(
        redis=in_memory_redis,
        user_id=str(user_account.id),
    )
    token_hash = session_manager.hash_refresh_token(token)

    client.cookies.clear()
    client.cookies.set(settings.REFRESH_TOKEN_COOKIE_NAME, token)
    response = client.post("/auth/logout")

    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"

    # Set-Cookie cleared
    set_cookie = response.headers.get("set-cookie", "")
    assert "Max-Age=0" in set_cookie or 'refresh_token=""' in set_cookie

    # Session revoked in Redis
    session_record = json.loads(in_memory_redis.store[f"session:{session_id}"])
    assert session_record["revoked"] is True
    assert f"refresh_token:{token_hash}" not in in_memory_redis.store


@pytest.mark.asyncio
async def test_oauth_exchange_sets_refresh_cookie(
    client, in_memory_redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    in_memory_redis.store["oauth_code:good-code"] = "507f1f77bcf86cd799439011"
    monkeypatch.setattr(login.security, "create_access_token", lambda subject, expires_delta: "oauth-token")

    response = client.post("/oauth/exchange", params={"code": "good-code"})

    assert response.status_code == 200
    assert response.json() == {"access_token": "oauth-token", "token_type": "Bearer"}

    # Cookie was set
    assert settings.REFRESH_TOKEN_COOKIE_NAME in response.cookies
    raw_token = response.cookies[settings.REFRESH_TOKEN_COOKIE_NAME]
    token_hash = session_manager.hash_refresh_token(raw_token)
    assert f"refresh_token:{token_hash}" in in_memory_redis.store


async def _awaitable(val):
    return val
