from __future__ import annotations

from types import SimpleNamespace

import pytest
from beanie import PydanticObjectId

from app.api import login
from app.core.config import settings


class FakeGoogleResponse:
    def __init__(self, status_code: int, payload: dict[str, str]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, str]:
        return self._payload


class FakeFlow:
    def __init__(self, scopes: list[str] | None = None, authorization_url: str = "https://accounts.google.com/o/oauth") -> None:
        self.code_verifier = "code-verifier-123"
        self.redirect_uri = None
        self._authorization_url = authorization_url
        self.credentials = SimpleNamespace(
            scopes=scopes or list(login.SCOPES),
            token="google-access-token",
        )
        self.fetch_calls: list[tuple[str | None, str | None]] = []

    def authorization_url(self, *, state: str, code_challenge_method: str):
        return self._authorization_url, state

    def fetch_token(self, *, code: str | None, code_verifier: str | None) -> None:
        self.fetch_calls.append((code, code_verifier))


class FakeSavableUser:
    def __init__(self, *, email: str, is_verified: bool = False, is_actived: bool = False, hashed_password: str = "old-hash") -> None:
        self.email = email
        self.is_verified = is_verified
        self.is_actived = is_actived
        self.hashed_password = hashed_password

    async def save(self, *args, **kwargs):
        return self


@pytest.mark.asyncio
async def test_login_access_token_rejects_invalid_credentials(client, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_authenticate(*, email: str, password: str):
        return None

    monkeypatch.setattr(login.crud, "authenticate", fake_authenticate)

    response = client.post(
        "/login/access-token",
        data={"username": "missing@example.com", "password": "StrongPass1!"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_login_access_token_rejects_inactive_user(client, inactive_user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_authenticate(*, email: str, password: str):
        return inactive_user_account

    monkeypatch.setattr(login.crud, "authenticate", fake_authenticate)

    response = client.post(
        "/login/access-token",
        data={"username": inactive_user_account.email, "password": "StrongPass1!"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user"


@pytest.mark.asyncio
async def test_login_access_token_rejects_unverified_user(client, unverified_user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    unverified_user_account.is_actived = True

    async def fake_authenticate(*, email: str, password: str):
        return unverified_user_account

    monkeypatch.setattr(login.crud, "authenticate", fake_authenticate)

    response = client.post(
        "/login/access-token",
        data={"username": unverified_user_account.email, "password": "StrongPass1!"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User is not verified"


@pytest.mark.asyncio
async def test_login_access_token_returns_signed_token(client, user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_authenticate(*, email: str, password: str):
        return user_account

    monkeypatch.setattr(login.crud, "authenticate", fake_authenticate)
    monkeypatch.setattr(login.security, "create_access_token", lambda subject, expires_delta: "signed-token")

    response = client.post(
        "/login/access-token",
        data={"username": user_account.email, "password": "StrongPass1!"},
    )

    assert response.status_code == 200
    assert response.json() == {"access_token": "signed-token", "token_type": "Bearer"}


@pytest.mark.asyncio
async def test_signup_rejects_weak_password(client, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_user_by_email(*, email: str):
        return None

    monkeypatch.setattr(login.crud, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(login, "is_strong_password", lambda password: False)

    response = client.post(
        "/signup",
        json={"email": "new@example.com", "password": "weak", "full_name": "New User"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Password too weak"


@pytest.mark.asyncio
async def test_signup_rejects_existing_verified_user(client, user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    user_account.is_verified = True

    async def fake_get_user_by_email(*, email: str):
        return user_account

    monkeypatch.setattr(login.crud, "get_user_by_email", fake_get_user_by_email)

    response = client.post(
        "/signup",
        json={"email": user_account.email, "password": "StrongPass1!", "full_name": "User"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "User already exists"


@pytest.mark.asyncio
async def test_signup_creates_user_and_schedules_verification_email(client, unverified_user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    sent_emails: list[dict[str, str]] = []
    email_data = SimpleNamespace(subject="Verify", html_content="<b>Verify</b>")

    async def fake_get_user_by_email(*, email: str):
        return None

    async def fake_create_user(*, user_create):
        return unverified_user_account

    monkeypatch.setattr(login.crud, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(login.crud, "create_user", fake_create_user)
    monkeypatch.setattr(login, "is_strong_password", lambda password: True)
    monkeypatch.setattr(login, "generate_password_reset_token", lambda email: "verify-token")
    monkeypatch.setattr(login, "generate_signup_verify_email", lambda email, token: email_data)
    monkeypatch.setattr(
        login,
        "send_email",
        lambda **kwargs: sent_emails.append(kwargs),
    )

    response = client.post(
        "/signup",
        json={"email": "new@example.com", "password": "StrongPass1!", "full_name": "New User"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == unverified_user_account.email
    assert sent_emails == [
        {
            "email_to": "new@example.com",
            "subject": "Verify",
            "html_content": "<b>Verify</b>",
        }
    ]


@pytest.mark.asyncio
async def test_signup_verify_rejects_invalid_token(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(login, "verify_password_reset_token", lambda token: None)

    response = client.get("/signup-verify", params={"token": "bad-token"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_signup_verify_rejects_missing_user(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(login, "verify_password_reset_token", lambda token: "ghost@example.com")

    async def fake_get_user_by_email(*, email: str):
        return None

    monkeypatch.setattr(login.crud, "get_user_by_email", fake_get_user_by_email)

    response = client.get("/signup-verify", params={"token": "token"})

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


@pytest.mark.asyncio
async def test_signup_verify_rejects_already_verified_user(client, user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    user_account.is_verified = True
    monkeypatch.setattr(login, "verify_password_reset_token", lambda token: user_account.email)

    async def fake_get_user_by_email(*, email: str):
        return user_account

    monkeypatch.setattr(login.crud, "get_user_by_email", fake_get_user_by_email)

    response = client.get("/signup-verify", params={"token": "token"})

    assert response.status_code == 400
    assert response.json()["detail"] == "User already verified"


@pytest.mark.asyncio
async def test_signup_verify_activates_user(client, monkeypatch: pytest.MonkeyPatch) -> None:
    pending_user = FakeSavableUser(email="unverified@example.com", is_verified=False, is_actived=False)
    monkeypatch.setattr(login, "verify_password_reset_token", lambda token: pending_user.email)

    async def fake_get_user_by_email(*, email: str):
        return pending_user

    monkeypatch.setattr(login.crud, "get_user_by_email", fake_get_user_by_email)

    response = client.get("/signup-verify", params={"token": "token"})

    assert response.status_code == 200
    assert response.json() == {"message": "User verified successfully"}
    assert pending_user.is_verified is True
    assert pending_user.is_actived is True


def test_login_test_token_returns_current_user(client, auth_overrides, user_account, user_public) -> None:
    auth_overrides(public_user=user_public, account=user_account)

    response = client.post("/login/test-token")

    assert response.status_code == 200
    assert response.json()["id"] == user_public.id
    assert response.json()["email"] == user_public.email


@pytest.mark.asyncio
async def test_reset_password_rejects_invalid_token(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(login, "verify_password_reset_token", lambda token: None)

    response = client.post("/reset-password", json={"token": "bad-token", "new_password": "StrongPass1!"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_reset_password_rejects_unknown_user(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(login, "verify_password_reset_token", lambda token: "ghost@example.com")

    async def fake_get_user_by_email(*, email: str):
        return None

    monkeypatch.setattr(login.crud, "get_user_by_email", fake_get_user_by_email)

    response = client.post("/reset-password", json={"token": "token", "new_password": "StrongPass1!"})

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


@pytest.mark.asyncio
async def test_reset_password_rejects_inactive_user(client, inactive_user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(login, "verify_password_reset_token", lambda token: inactive_user_account.email)

    async def fake_get_user_by_email(*, email: str):
        return inactive_user_account

    monkeypatch.setattr(login.crud, "get_user_by_email", fake_get_user_by_email)

    response = client.post("/reset-password", json={"token": "token", "new_password": "StrongPass1!"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"


@pytest.mark.asyncio
async def test_reset_password_updates_password(client, monkeypatch: pytest.MonkeyPatch) -> None:
    user_account = FakeSavableUser(email="user@example.com", is_verified=True, is_actived=True)

    async def fake_get_user_by_email(*, email: str):
        return user_account

    monkeypatch.setattr(login, "verify_password_reset_token", lambda token: user_account.email)
    monkeypatch.setattr(login.crud, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(login.security, "get_password_hash", lambda password: "new-hash")

    response = client.post("/reset-password", json={"token": "token", "new_password": "StrongPass1!"})

    assert response.status_code == 200
    assert response.json() == {"message": "Password update successfuly"}
    assert user_account.hashed_password == "new-hash"


@pytest.mark.asyncio
async def test_password_recovery_rejects_unknown_email(client, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_user_by_email(*, email: str):
        return None

    monkeypatch.setattr(login.crud, "get_user_by_email", fake_get_user_by_email)

    response = client.post("/password-recovery/missing@example.com")

    assert response.status_code == 404
    assert response.json()["detail"] == "This user is not registered"


@pytest.mark.asyncio
async def test_password_recovery_sends_reset_email(client, user_account, monkeypatch: pytest.MonkeyPatch) -> None:
    sent_emails: list[dict[str, str]] = []
    email_data = SimpleNamespace(subject="Reset", html_content="<b>Reset</b>")

    async def fake_get_user_by_email(*, email: str):
        return user_account

    monkeypatch.setattr(login.crud, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(login, "generate_password_reset_token", lambda email: "reset-token")
    monkeypatch.setattr(login, "generate_reset_password_email", lambda email_to, email, token: email_data)
    monkeypatch.setattr(login, "send_email", lambda **kwargs: sent_emails.append(kwargs))

    response = client.post(f"/password-recovery/{user_account.email}")

    assert response.status_code == 200
    assert response.json() == {"message": "Password recovery email sent"}
    assert sent_emails == [
        {
            "email_to": user_account.email,
            "subject": "Reset",
            "html_content": "<b>Reset</b>",
        }
    ]


def test_auth_google_redirects_and_sets_oauth_cookies(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(login.secrets, "token_urlsafe", lambda _length: "oauth-state")
    fake_flow = FakeFlow()
    monkeypatch.setattr(login.Flow, "from_client_secrets_file", lambda *args, **kwargs: fake_flow)

    response = client.get("/auth/google", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "https://accounts.google.com/o/oauth"
    assert "oauth_state=oauth-state" in response.headers.get("set-cookie", "")
    assert "oauth_code_verifier=code-verifier-123" in response.headers.get("set-cookie", "")


def test_callback_rejects_invalid_state(client) -> None:
    response = client.get(
        "/auth/google/callback",
        params={"state": "request-state", "code": "auth-code"},
        cookies={"oauth_state": "cookie-state", "oauth_code_verifier": "verifier"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid state"


def test_callback_rejects_missing_code_verifier(client) -> None:
    response = client.get(
        "/auth/google/callback",
        params={"state": "same-state", "code": "auth-code"},
        cookies={"oauth_state": "same-state"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing code verifier"


def test_callback_rejects_missing_required_scopes(client, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_flow = FakeFlow(scopes=[login.SCOPES[0]])
    monkeypatch.setattr(login.Flow, "from_client_secrets_file", lambda *args, **kwargs: fake_flow)

    response = client.get(
        "/auth/google/callback",
        params={"state": "same-state", "code": "auth-code"},
        cookies={"oauth_state": "same-state", "oauth_code_verifier": "verifier"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing required scopes"


def test_callback_creates_exchange_code_and_redirects(client, in_memory_redis, oauth_account, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeOauthAccount:
        def __init__(self, **kwargs) -> None:
            self.__dict__.update(kwargs)
            self.id = PydanticObjectId()

    monkeypatch.setattr(settings, "FRONTEND_URL", "http://frontend.local")
    monkeypatch.setattr(login.secrets, "token_urlsafe", lambda _length: "exchange-code")
    monkeypatch.setattr(login.Flow, "from_client_secrets_file", lambda *args, **kwargs: FakeFlow())
    monkeypatch.setattr(login, "Oauth2Account", FakeOauthAccount)
    monkeypatch.setattr(
        login.requests,
        "get",
        lambda url, headers: FakeGoogleResponse(200, {"email": oauth_account.email, "name": oauth_account.name, "id": oauth_account.provider_account_id}),
    )

    async def fake_get_oauth_account_by_email(*, email: str):
        return None

    async def fake_create_oauth2_account(*, oauth_account):
        return oauth_account

    monkeypatch.setattr(login.crud, "get_oauth_account_by_email", fake_get_oauth_account_by_email)
    monkeypatch.setattr(login.crud, "create_oauth2_account", fake_create_oauth2_account)

    response = client.get(
        "/auth/google/callback",
        params={"state": "same-state", "code": "auth-code"},
        cookies={"oauth_state": "same-state", "oauth_code_verifier": "verifier"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "http://frontend.local/oauth/exchange?code=exchange-code"
    assert in_memory_redis.store["oauth_code:exchange-code"]


def test_oauth_exchange_rejects_invalid_code(client) -> None:
    response = client.post("/oauth/exchange", params={"code": "bad-code"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired code"


def test_oauth_exchange_returns_access_token(client, in_memory_redis, monkeypatch: pytest.MonkeyPatch) -> None:
    in_memory_redis.store["oauth_code:good-code"] = "user-id-123"
    monkeypatch.setattr(login.security, "create_access_token", lambda subject, expires_delta: "oauth-token")

    response = client.post("/oauth/exchange", params={"code": "good-code"})

    assert response.status_code == 200
    assert response.json() == {"access_token": "oauth-token", "token_type": "Bearer"}
    assert "oauth_code:good-code" not in in_memory_redis.store



