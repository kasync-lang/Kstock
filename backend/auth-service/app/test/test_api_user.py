from __future__ import annotations

from types import SimpleNamespace

import pytest
from beanie import PydanticObjectId

from app.api import user as user_api


class FindUsersQuery:
    def __init__(self, users):
        self.users = users
        self.skipped = None
        self.limited = None
        self.length = None

    def skip(self, value: int):
        self.skipped = value
        return self

    def limit(self, value: int):
        self.limited = value
        return self

    async def to_list(self, length: int):
        self.length = length
        return self.users


class UpdateQuery:
    def __init__(self, result=None):
        self.result = result
        self.payload = None

    async def update(self, payload):
        self.payload = payload
        return self.result


class AwaitableValue:
    def __init__(self, value):
        self.value = value

    def __await__(self):
        async def _inner():
            return self.value

        return _inner().__await__()


class EditableDoc:
    def __init__(self) -> None:
        self.payload = None

    async def update(self, payload):
        self.payload = payload
        return self


class SavableAccount(SimpleNamespace):
    async def save(self):
        return self


@pytest.mark.asyncio
async def test_read_users_returns_paginated_users(client, auth_overrides, superuser_account, superuser_public, user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=superuser_public, account=superuser_account, superuser=True)
    query = FindUsersQuery([user_account, superuser_account])
    monkeypatch.setattr(user_api.User, "find", staticmethod(lambda *_args, **_kwargs: query))

    response = client.get("/user/", params={"skip": 2, "limit": 5})

    assert response.status_code == 200
    assert len(response.json()["data"]) == 2
    assert query.skipped == 5
    assert query.limited == 5
    assert query.length == 5


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_email(client, auth_overrides, superuser_account, superuser_public, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=superuser_public, account=superuser_account, superuser=True)

    async def fake_get_user_by_email(*, email: str):
        return object()

    monkeypatch.setattr(user_api.crud, "get_user_by_email", fake_get_user_by_email)

    response = client.post(
        "/user/",
        json={"email": "existing@example.com", "password": "StrongPass1!", "full_name": "Existing User"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "User already exists"


@pytest.mark.asyncio
async def test_create_user_creates_account_and_sends_email(client, auth_overrides, superuser_account, superuser_public, user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=superuser_public, account=superuser_account, superuser=True)
    sent_emails: list[tuple[str, str, str]] = []
    monkeypatch.setattr(user_api, "settings", SimpleNamespace(emails_enabled=True))

    async def fake_get_user_by_email(*, email: str):
        return None

    async def fake_create_user(*, user_create):
        return user_account

    monkeypatch.setattr(user_api.crud, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(user_api.crud, "create_user", fake_create_user)
    monkeypatch.setattr(
        user_api,
        "generate_new_account_email",
        lambda email_to, username, password: SimpleNamespace(subject="Welcome", html_content="<b>Welcome</b>"),
    )
    monkeypatch.setattr(user_api, "send_email", lambda email_to, subject, html_content: sent_emails.append((email_to, subject, html_content)))

    response = client.post(
        "/user/",
        json={"email": "user@example.com", "password": "StrongPass1!", "full_name": "Regular User"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == user_account.email
    assert sent_emails == [("user@example.com", "Welcome", "<b>Welcome</b>")]


@pytest.mark.asyncio
async def test_update_user_me_rejects_oauth_account(client, auth_overrides, oauth_account, oauth_public) -> None:
    auth_overrides(public_user=oauth_public, account=oauth_account)

    response = client.patch("/user/me", json={"email": "oauth@example.com", "full_name": "OAuth User"})

    assert response.status_code == 400
    assert response.json()["detail"] == "OAuth account profile is managed by its provider"


@pytest.mark.asyncio
async def test_update_user_me_rejects_duplicate_email(client, auth_overrides, user_account, user_public, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=user_public, account=user_account)
    other_user = SimpleNamespace(id=str(PydanticObjectId()))

    async def fake_get_user_by_email(*, email: str):
        return other_user

    monkeypatch.setattr(user_api.crud, "get_user_by_email", fake_get_user_by_email)

    response = client.patch("/user/me", json={"email": "taken@example.com", "full_name": "Regular User"})

    assert response.status_code == 409
    assert response.json()["detail"] == "User with this email already exists"


@pytest.mark.asyncio
async def test_update_user_me_updates_profile(client, auth_overrides, user_account, user_public, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=user_public, account=user_account)
    monkeypatch.setattr(user_api.User, "id", object(), raising=False)

    async def fake_get_user_by_email(*, email: str):
        return None

    editable_doc = EditableDoc()
    updated_user = user_account.model_copy(update={"email": "updated@example.com", "full_name": "Updated User"})
    find_one_calls = iter([AwaitableValue(editable_doc), AwaitableValue(updated_user)])

    monkeypatch.setattr(user_api.crud, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(user_api.User, "find_one", staticmethod(lambda *_args, **_kwargs: next(find_one_calls)))

    response = client.patch("/user/me", json={"email": "updated@example.com", "full_name": "Updated User"})

    assert response.status_code == 200
    assert response.json()["email"] == "updated@example.com"
    assert response.json()["full_name"] == "Updated User"


@pytest.mark.asyncio
async def test_update_user_password_me_rejects_oauth_account(client, auth_overrides, oauth_account, oauth_public) -> None:
    auth_overrides(public_user=oauth_public, account=oauth_account)

    response = client.patch(
        "/user/me/password",
        json={"current_password": "OldPass1!", "new_password": "NewPass1!"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "OAuth accounts do not have a local password"


@pytest.mark.asyncio
async def test_update_user_password_me_rejects_wrong_password(client, auth_overrides, user_account, user_public, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=user_public, account=user_account)
    monkeypatch.setattr(user_api, "verify_password", lambda plain, hashed: False)

    response = client.patch(
        "/user/me/password",
        json={"current_password": "WrongPass1!", "new_password": "NewPass1!"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect password"


@pytest.mark.asyncio
async def test_update_user_password_me_rejects_same_password(client, auth_overrides, user_account, user_public, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=user_public, account=user_account)
    monkeypatch.setattr(user_api, "verify_password", lambda plain, hashed: True)

    response = client.patch(
        "/user/me/password",
        json={"current_password": "SamePass1!", "new_password": "SamePass1!"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "New password can not be the same current password"


@pytest.mark.asyncio
async def test_update_user_password_me_updates_hash(client, auth_overrides, user_account, user_public, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=user_public, account=user_account)
    query = UpdateQuery(result=None)
    monkeypatch.setattr(user_api.User, "id", object(), raising=False)
    monkeypatch.setattr(user_api, "verify_password", lambda plain, hashed: True)
    monkeypatch.setattr(user_api, "get_password_hash", lambda password: "new-password-hash")
    monkeypatch.setattr(user_api.User, "find_one", staticmethod(lambda *_args, **_kwargs: query))

    response = client.patch(
        "/user/me/password",
        json={"current_password": "OldPass1!", "new_password": "NewPass1!"},
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Password updated successfully"}
    assert query.payload == {"$set": {"hashed_password": "new-password-hash"}}


def test_read_user_me_returns_current_user(client, auth_overrides, user_account, user_public) -> None:
    auth_overrides(public_user=user_public, account=user_account)

    response = client.get("/user/me")

    assert response.status_code == 200
    assert response.json()["id"] == user_public.id


@pytest.mark.asyncio
async def test_delete_user_me_rejects_superuser(client, auth_overrides, superuser_account, superuser_public) -> None:
    auth_overrides(public_user=superuser_public, account=superuser_account)

    response = client.delete("/user/me")

    assert response.status_code == 403
    assert response.json()["detail"] == "Superuser can not be deleted yourself"


@pytest.mark.asyncio
async def test_delete_user_me_returns_400_on_save_error(client, auth_overrides, user_account, user_public) -> None:
    current_account = SavableAccount(id=user_public.id, email=user_public.email, hashed_password="hash", is_actived=True)

    async def failing_save():
        raise RuntimeError("save failed")

    current_account.save = failing_save
    auth_overrides(public_user=user_public, account=current_account)

    response = client.delete("/user/me")

    assert response.status_code == 400
    assert response.json()["detail"] == "Something went wrong"


@pytest.mark.asyncio
async def test_delete_user_me_deactivates_account(client, auth_overrides, user_account, user_public) -> None:
    current_account = SavableAccount(id=user_public.id, email=user_public.email, hashed_password="hash", is_actived=True)
    auth_overrides(public_user=user_public, account=current_account)

    response = client.delete("/user/me")

    assert response.status_code == 200
    assert response.json() == {"message": "User deleted successfully"}
    assert current_account.is_actived is False


@pytest.mark.asyncio
async def test_read_user_by_id_rejects_invalid_id(client, auth_overrides, user_account, user_public) -> None:
    auth_overrides(public_user=user_public, account=user_account)

    response = client.get("/user/not-a-valid-id")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found in system"


@pytest.mark.asyncio
async def test_read_user_by_id_rejects_missing_user(client, auth_overrides, user_account, user_public, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=user_public, account=user_account)
    monkeypatch.setattr(user_api.User, "get", staticmethod(lambda account_id: _awaitable(None)))
    monkeypatch.setattr(user_api.Oauth2Account, "get", staticmethod(lambda account_id: _awaitable(None)))

    response = client.get(f"/user/{PydanticObjectId()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found in system"


@pytest.mark.asyncio
async def test_read_user_by_id_returns_self_for_current_user(client, auth_overrides, user_account, user_public, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=user_public, account=user_account)
    monkeypatch.setattr(user_api.User, "get", staticmethod(lambda account_id: _awaitable(user_account)))
    monkeypatch.setattr(user_api.Oauth2Account, "get", staticmethod(lambda account_id: _awaitable(None)))

    response = client.get(f"/user/{user_account.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(user_account.id)


@pytest.mark.asyncio
async def test_read_user_by_id_rejects_other_user_for_non_admin(client, auth_overrides, user_account, user_public, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=user_public, account=user_account)
    other_user = user_account.model_copy(update={"id": PydanticObjectId(), "email": "other@example.com"})
    monkeypatch.setattr(user_api.User, "get", staticmethod(lambda account_id: _awaitable(other_user)))
    monkeypatch.setattr(user_api.Oauth2Account, "get", staticmethod(lambda account_id: _awaitable(None)))

    response = client.get(f"/user/{other_user.id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden"


@pytest.mark.asyncio
async def test_read_user_by_id_allows_superuser_to_read_other_user(client, auth_overrides, superuser_account, superuser_public, user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=superuser_public, account=superuser_account, superuser=True)
    monkeypatch.setattr(user_api.User, "get", staticmethod(lambda account_id: _awaitable(user_account)))
    monkeypatch.setattr(user_api.Oauth2Account, "get", staticmethod(lambda account_id: _awaitable(None)))

    response = client.get(f"/user/{user_account.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(user_account.id)


@pytest.mark.asyncio
async def test_update_user_returns_404_when_user_missing(client, auth_overrides, superuser_account, superuser_public, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=superuser_public, account=superuser_account, superuser=True)
    monkeypatch.setattr(user_api.User, "id", object(), raising=False)
    monkeypatch.setattr(user_api.User, "find_one", staticmethod(lambda *_args, **_kwargs: AwaitableValue(None)))

    response = client.patch(
        f"/user/{PydanticObjectId()}",
        json={"email": "updated@example.com", "full_name": "Updated User"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found in system"


@pytest.mark.asyncio
async def test_update_user_rejects_duplicate_email(client, auth_overrides, superuser_account, superuser_public, user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=superuser_public, account=superuser_account, superuser=True)
    other_user = SimpleNamespace(id=str(PydanticObjectId()))
    monkeypatch.setattr(user_api.User, "id", object(), raising=False)

    async def fake_get_user_by_email(*, email: str):
        return other_user

    monkeypatch.setattr(user_api.User, "find_one", staticmethod(lambda *_args, **_kwargs: AwaitableValue(user_account)))
    monkeypatch.setattr(user_api.crud, "get_user_by_email", fake_get_user_by_email)

    response = client.patch(
        f"/user/{PydanticObjectId()}",
        json={"email": "taken@example.com", "full_name": "Updated User"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "User with this email already exists"


@pytest.mark.asyncio
async def test_update_user_updates_user_for_superuser(client, auth_overrides, superuser_account, superuser_public, user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=superuser_public, account=superuser_account, superuser=True)
    updated_user = user_account.model_copy(update={"email": "updated@example.com", "full_name": "Updated User"})
    monkeypatch.setattr(user_api.User, "id", object(), raising=False)
    find_one_calls = iter([
        AwaitableValue(user_account),
        UpdateQuery(result=updated_user),
    ])

    async def fake_get_user_by_email(*, email: str):
        return None

    monkeypatch.setattr(user_api.crud, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(user_api.User, "find_one", staticmethod(lambda *_args, **_kwargs: next(find_one_calls)))

    response = client.patch(
        f"/user/{PydanticObjectId()}",
        json={"email": "updated@example.com", "full_name": "Updated User"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "updated@example.com"


@pytest.mark.asyncio
async def test_delete_user_returns_404_when_user_missing(client, auth_overrides, superuser_account, superuser_public, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=superuser_public, account=superuser_account, superuser=True)
    monkeypatch.setattr(user_api.User, "id", object(), raising=False)
    monkeypatch.setattr(user_api.User, "find_one", staticmethod(lambda *_args, **_kwargs: AwaitableValue(None)))

    response = client.delete(f"/user/{PydanticObjectId()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found in system"


@pytest.mark.asyncio
async def test_delete_user_rejects_deleting_current_superuser(client, auth_overrides, superuser_account, superuser_public, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=superuser_public, account=superuser_account, superuser=True)
    monkeypatch.setattr(user_api.User, "id", object(), raising=False)
    monkeypatch.setattr(user_api.User, "find_one", staticmethod(lambda *_args, **_kwargs: AwaitableValue(superuser_account)))

    response = client.delete(f"/user/{superuser_account.id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Can not delete superuser yourself"


@pytest.mark.asyncio
async def test_delete_user_marks_user_inactive(client, auth_overrides, superuser_account, superuser_public, user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    auth_overrides(public_user=superuser_public, account=superuser_account, superuser=True)
    monkeypatch.setattr(user_api.User, "id", object(), raising=False)
    monkeypatch.setattr(user_api.User, "find_one", staticmethod(lambda *_args, **_kwargs: AwaitableValue(user_account)))

    response = client.delete(f"/user/{user_account.id}")

    assert response.status_code == 200
    assert response.json() == {"message": "User deleted successfully"}
    assert user_account.is_actived is False


async def _return_value(value):
    return value


def _awaitable(value):
    return _return_value(value)


