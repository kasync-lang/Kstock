from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import crud
from app.schema.user import UserCreate, UserUpdate


class FakeUserDocument:
    email = object()

    def __init__(self, **data):
        self.__dict__.update(data)
        self.saved = False

    async def save(self) -> None:
        self.saved = True


class FakePersistedUser:
    def __init__(self) -> None:
        self.email = "old@example.com"
        self.hashed_password = "old-hash"
        self.saved = False

    async def save(self) -> None:
        self.saved = True


class FakeOauthAccountDocument:
    email = object()

    def __init__(self, **data):
        self.__dict__.update(data)
        self.saved = False

    async def save(self) -> None:
        self.saved = True


class FakeOauthInput:
    def __init__(self, **data):
        self._data = data

    def model_dump(self):
        return dict(self._data)


@pytest.mark.asyncio
async def test_create_user_hashes_password_and_saves_new_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crud, "User", FakeUserDocument)
    monkeypatch.setattr(crud, "get_password_hash", lambda password: f"hashed::{password}")

    async def fake_get_user_by_email(*, email: str):
        return None

    monkeypatch.setattr(crud, "get_user_by_email", fake_get_user_by_email)

    result = await crud.create_user(
        user_create=UserCreate(
            email="new@example.com",
            password="StrongPass1!",
            full_name="New User",
        )
    )

    assert result.email == "new@example.com"
    assert result.hashed_password == "hashed::StrongPass1!"
    assert result.role == "basic_user"
    assert result.saved is True


@pytest.mark.asyncio
async def test_create_user_returns_unsaved_object_when_email_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crud, "User", FakeUserDocument)
    monkeypatch.setattr(crud, "get_password_hash", lambda password: f"hashed::{password}")

    async def fake_get_user_by_email(*, email: str):
        return object()

    monkeypatch.setattr(crud, "get_user_by_email", fake_get_user_by_email)

    result = await crud.create_user(
        user_create=UserCreate(
            email="existing@example.com",
            password="StrongPass1!",
            full_name="Existing User",
        )
    )

    assert result.email == "existing@example.com"
    assert result.saved is False


@pytest.mark.asyncio
async def test_update_user_updates_email_and_password_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crud, "get_password_hash", lambda password: f"hashed::{password}")
    user = FakePersistedUser()

    result = await crud.update_user(
        db_user=user,
        user_in=UserUpdate(email="updated@example.com", password="StrongPass1!"),
    )

    assert result is user
    assert user.email == "updated@example.com"
    assert user.hashed_password == "hashed::StrongPass1!"
    assert user.saved is True


@pytest.mark.asyncio
async def test_get_user_by_email_delegates_to_user_find_one(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeUserModel:
        email = object()

        @staticmethod
        async def find_one(_query):
            return "user-result"

    monkeypatch.setattr(crud, "User", FakeUserModel)

    assert await crud.get_user_by_email(email="user@example.com") == "user-result"


@pytest.mark.asyncio
async def test_get_oauth_account_by_email_delegates_to_find_one(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeOauthModel:
        email = object()

        @staticmethod
        async def find_one(_query):
            return "oauth-result"

    monkeypatch.setattr(crud, "Oauth2Account", FakeOauthModel)

    assert await crud.get_oauth_account_by_email(email="oauth@example.com") == "oauth-result"


@pytest.mark.asyncio
async def test_authenticate_returns_none_when_user_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_user_by_email(*, email: str):
        return None

    monkeypatch.setattr(crud, "get_user_by_email", fake_get_user_by_email)

    assert await crud.authenticate(email="missing@example.com", password="StrongPass1!") is None


@pytest.mark.asyncio
async def test_authenticate_returns_none_when_password_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(hashed_password="hash")

    async def fake_get_user_by_email(*, email: str):
        return user

    monkeypatch.setattr(crud, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(crud, "verify_password", lambda password, hashed: False)

    assert await crud.authenticate(email="user@example.com", password="wrong") is None


@pytest.mark.asyncio
async def test_authenticate_returns_user_when_password_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(hashed_password="hash", email="user@example.com")

    async def fake_get_user_by_email(*, email: str):
        return user

    monkeypatch.setattr(crud, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(crud, "verify_password", lambda password, hashed: True)

    assert await crud.authenticate(email="user@example.com", password="StrongPass1!") is user


@pytest.mark.asyncio
async def test_create_oauth2_account_saves_new_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crud, "Oauth2Account", FakeOauthAccountDocument)

    async def fake_get_oauth_account_by_email(*, email: str):
        return None

    monkeypatch.setattr(crud, "get_oauth_account_by_email", fake_get_oauth_account_by_email)

    oauth_input = FakeOauthInput(
        provider="google",
        email="oauth@example.com",
        provider_account_id="google-123",
        name="OAuth User",
        scope=["openid", "email"],
        is_actived=True,
        role="basic_user",
    )

    result = await crud.create_oauth2_account(oauth_account=oauth_input)

    assert result.email == "oauth@example.com"
    assert result.saved is True


@pytest.mark.asyncio
async def test_create_oauth2_account_returns_unsaved_object_when_email_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crud, "Oauth2Account", FakeOauthAccountDocument)

    async def fake_get_oauth_account_by_email(*, email: str):
        return object()

    monkeypatch.setattr(crud, "get_oauth_account_by_email", fake_get_oauth_account_by_email)

    oauth_input = FakeOauthInput(
        provider="google",
        email="oauth@example.com",
        provider_account_id="google-123",
        name="OAuth User",
        scope=["openid", "email"],
        is_actived=True,
        role="basic_user",
    )

    result = await crud.create_oauth2_account(oauth_account=oauth_input)

    assert result.email == "oauth@example.com"
    assert result.saved is False


