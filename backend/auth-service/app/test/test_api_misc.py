from __future__ import annotations

from types import SimpleNamespace

from app.api import testutil
from app.core.config import KeyStore


def test_get_jwk_returns_public_key_data(client) -> None:
    response = client.get("/.well-known/jwk")

    assert response.status_code == 200
    body = response.json()
    assert "jwk_data" in body
    assert body["jwk_data"]["kty"] == "RSA"


def test_get_jwk_returns_404_when_public_key_is_missing(client, monkeypatch) -> None:
    monkeypatch.setattr(KeyStore, "public_key", None)

    response = client.get("/.well-known/jwk")

    assert response.status_code == 404
    assert response.json()["detail"] == "JWK not found"


def test_task_send_email_uses_email_helper(monkeypatch) -> None:
    calls: dict[str, object] = {}
    email_data = SimpleNamespace(subject="Test", html_content="<b>body</b>")
    monkeypatch.setattr(testutil, "generate_test_email", lambda email_to: email_data)
    monkeypatch.setattr(
        testutil,
        "send_email",
        lambda **kwargs: calls.update(kwargs),
    )

    testutil.task_send_email("user@example.com")

    assert calls == {
        "email_to": "user@example.com",
        "subject": "Test",
        "html_content": "<b>body</b>",
    }


def test_test_email_endpoint_sends_email_for_superuser(client, auth_overrides, superuser_account, superuser_public, monkeypatch) -> None:
    auth_overrides(public_user=superuser_public, account=superuser_account, superuser=True)
    email_data = SimpleNamespace(subject="Test email", html_content="<b>body</b>")
    calls: dict[str, object] = {}
    monkeypatch.setattr(testutil, "generate_test_email", lambda email_to: email_data)
    monkeypatch.setattr(testutil, "send_email", lambda **kwargs: calls.update(kwargs))

    response = client.post("/utils/test-email/", params={"email_to": "user@example.com"})

    assert response.status_code == 201
    assert response.json() == {"message": "Test email sent"}
    assert calls["email_to"] == "user@example.com"


def test_health_check_returns_true(client) -> None:
    response = client.get("/utils/health-check/")

    assert response.status_code == 200
    assert response.json() is True

