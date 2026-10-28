from __future__ import annotations

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


def test_test_email_endpoint_queues_email_for_superuser(client, auth_overrides, superuser_account, superuser_public, sent_emails) -> None:
    auth_overrides(public_user=superuser_public, account=superuser_account, superuser=True)

    response = client.post("/utils/test-email/", params={"email_to": "user@example.com"})

    assert response.status_code == 201
    assert response.json() == {"message": "Test email queued"}
    assert sent_emails == [
        {"template": "test_email", "to": "user@example.com", "data": {"email": "user@example.com"}}
    ]


def test_health_check_returns_true(client) -> None:
    response = client.get("/utils/health-check/")

    assert response.status_code == 200
    assert response.json() is True

