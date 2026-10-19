from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException
from fastapi import Request
from jwt.exceptions import InvalidTokenError

from app.api import deps
from app.schema.user import UserPublic


def test_get_redis_returns_request_app_redis(in_memory_redis) -> None:
    scope = {"type": "http", "app": type("App", (), {"state": type("State", (), {"redis": in_memory_redis})()})()}
    request = Request(scope)

    assert deps.get_redis(request) is in_memory_redis


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_decode(*args, **kwargs):
        raise InvalidTokenError("bad token")

    monkeypatch.setattr(deps.jwt, "decode", fake_decode)

    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user("bad-token")

    assert exc.value.status_code == 401
    assert exc.value.detail == {"code": "INVALID_TOKEN", "message": "Token is invalid"}


@pytest.mark.asyncio
async def test_get_current_user_rejects_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_decode(*args, **kwargs):
        raise jwt.ExpiredSignatureError("Signature has expired")

    monkeypatch.setattr(deps.jwt, "decode", fake_decode)

    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user("expired-token")

    assert exc.value.status_code == 401
    assert exc.value.detail == {"code": "ACCESS_TOKEN_EXPIRED", "message": "Access token has expired"}


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        deps.jwt,
        "decode",
        lambda *args, **kwargs: {"sub": "not-an-object-id", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
    )

    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user("token")

    assert exc.value.status_code == 401
    assert exc.value.detail == {"code": "INVALID_TOKEN", "message": "Token is invalid"}


@pytest.mark.asyncio
async def test_get_current_user_returns_local_user(user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = str(user_account.id)
    monkeypatch.setattr(
        deps.jwt,
        "decode",
        lambda *args, **kwargs: {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
    )
    monkeypatch.setattr(deps.User, "get", staticmethod(lambda account_id: _awaitable(user_account)))
    monkeypatch.setattr(deps.Oauth2Account, "get", staticmethod(lambda account_id: _awaitable(None)))

    result = await deps.get_current_user("good-token")

    assert result is user_account


@pytest.mark.asyncio
async def test_get_current_user_falls_back_to_oauth_account(oauth_account, monkeypatch: pytest.MonkeyPatch) -> None:
    account_id = str(oauth_account.id)
    monkeypatch.setattr(
        deps.jwt,
        "decode",
        lambda *args, **kwargs: {"sub": account_id, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
    )
    monkeypatch.setattr(deps.User, "get", staticmethod(lambda account_id: _awaitable(None)))
    monkeypatch.setattr(deps.Oauth2Account, "get", staticmethod(lambda account_id: _awaitable(oauth_account)))

    result = await deps.get_current_user("good-token")

    assert result is oauth_account


@pytest.mark.asyncio
async def test_get_current_user_raises_404_when_account_does_not_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    account_id = str(PydanticObjectId())
    monkeypatch.setattr(
        deps.jwt,
        "decode",
        lambda *args, **kwargs: {"sub": account_id, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
    )
    monkeypatch.setattr(deps.User, "get", staticmethod(lambda account_id: _awaitable(None)))
    monkeypatch.setattr(deps.Oauth2Account, "get", staticmethod(lambda account_id: _awaitable(None)))

    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user("good-token")

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_current_user_rejects_inactive_account(inactive_user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = str(inactive_user_account.id)
    monkeypatch.setattr(
        deps.jwt,
        "decode",
        lambda *args, **kwargs: {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
    )
    monkeypatch.setattr(deps.User, "get", staticmethod(lambda account_id: _awaitable(inactive_user_account)))
    monkeypatch.setattr(deps.Oauth2Account, "get", staticmethod(lambda account_id: _awaitable(None)))

    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user("good-token")

    assert exc.value.status_code == 400
    assert exc.value.detail == "Inactive user"


def test_parse_user_db_to_currentuser_maps_local_user(user_account) -> None:
    current_user = deps.parse_user_db_to_currentuser(user_account)

    assert isinstance(current_user, UserPublic)
    assert current_user.id == str(user_account.id)
    assert current_user.email == user_account.email
    assert current_user.full_name == user_account.full_name
    assert current_user.provider is None
    assert current_user.is_superuser is False


def test_parse_user_db_to_currentuser_maps_oauth_user(oauth_account) -> None:
    current_user = deps.parse_user_db_to_currentuser(oauth_account)

    assert current_user.id == str(oauth_account.id)
    assert current_user.email == oauth_account.email
    assert current_user.full_name == oauth_account.name
    assert current_user.provider == "google"
    assert current_user.is_superuser is False


def test_get_current_active_superuser_rejects_basic_user(user_public) -> None:
    with pytest.raises(HTTPException) as exc:
        deps.get_current_active_superuser(user_public)

    assert exc.value.status_code == 403


def test_get_current_active_superuser_returns_admin(superuser_public) -> None:
    assert deps.get_current_active_superuser(superuser_public) is superuser_public


@pytest.mark.asyncio
async def test_custom_oauth2_bearer_missing_token() -> None:
    scheme = deps.CustomOAuth2PasswordBearer(tokenUrl="/login", auto_error=False)
    scope = {"type": "http", "headers": []}
    request = Request(scope)

    with pytest.raises(HTTPException) as exc:
        await scheme(request)

    assert exc.value.status_code == 401
    assert exc.value.detail == {"code": "MISSING_TOKEN", "message": "Bearer token is required"}


@pytest.mark.asyncio
async def test_custom_oauth2_bearer_non_bearer_token() -> None:
    scheme = deps.CustomOAuth2PasswordBearer(tokenUrl="/login", auto_error=False)
    scope = {"type": "http", "headers": [(b"authorization", b"Basic 123456")]}
    request = Request(scope)

    with pytest.raises(HTTPException) as exc:
        await scheme(request)

    assert exc.value.status_code == 401
    assert exc.value.detail == {"code": "MISSING_TOKEN", "message": "Bearer token is required"}


def test_endpoint_missing_token_returns_standard_response(client) -> None:
    response = client.post("/login/test-token")

    assert response.status_code == 401
    assert response.json() == {
        "code": "MISSING_TOKEN",
        "message": "Bearer token is required",
    }


def test_endpoint_expired_token_returns_standard_response(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_decode(*args, **kwargs):
        raise jwt.ExpiredSignatureError("Token expired")

    monkeypatch.setattr(deps.jwt, "decode", fake_decode)

    response = client.post(
        "/login/test-token",
        headers={"Authorization": "Bearer expired.jwt.token"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "ACCESS_TOKEN_EXPIRED",
        "message": "Access token has expired",
    }


def test_endpoint_invalid_token_returns_standard_response(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_decode(*args, **kwargs):
        raise InvalidTokenError("Invalid token format")

    monkeypatch.setattr(deps.jwt, "decode", fake_decode)

    response = client.post(
        "/login/test-token",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "INVALID_TOKEN",
        "message": "Token is invalid",
    }


async def _return_value(value):
    return value


def _awaitable(value):
    return _return_value(value)
