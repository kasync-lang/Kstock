from __future__ import annotations

from app.core import config as config_module
from app.core.config import KeyStore, Setting, parse_cors
import pytest


def test_parse_cors_splits_comma_separated_string() -> None:
    assert parse_cors("http://localhost:3000, http://example.com") == [
        "http://localhost:3000",
        "http://example.com",
    ]


def test_parse_cors_returns_list_as_is() -> None:
    values = ["http://localhost:3000", "http://example.com"]
    assert parse_cors(values) == values


def test_keystore_load_key_reads_key_files(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = b"private-test-key"
    public_key = b"public-test-key"
    (tmp_path / "private.pem").write_bytes(private_key)
    (tmp_path / "public.pem").write_bytes(public_key)
    (tmp_path / "client_secret.json").write_text("{}")

    monkeypatch.setattr(config_module, "KEY_DIR", str(tmp_path))
    KeyStore.private_key = None
    KeyStore.public_key = None

    KeyStore.load_key()

    assert KeyStore.private_key == private_key
    assert KeyStore.public_key == public_key


def test_setting_computed_fields_and_email_flag() -> None:
    settings = Setting(
        REDIS_HOST="localhost",
        REDIS_PORT=6379,
        MONGO_URI="mongodb://localhost:27017",
        FRONTEND_HOST="http://frontend.local",
        FIRST_SUPERUSER="admin@example.com",
        FIRST_SUPERUSER_EMAIL="admin@example.com",
        FIRST_SUPERUSER_PASSWORD="StrongPass1!",
        ALGORITHM="RS256",
        ACCESS_TOKEN_EXPIRE_MINUTES=30,
        BACKEND_CORS_ORIGINS="http://api.local, http://admin.local",
        SMTP_HOST="smtp.local",
        EMAILS_FROM_EMAIL="noreply@example.com",
        EMAILS_FROM_NAME="sender@example.com",
        PROJECT_NAME="Auth Test",
    )

    assert settings.all_cors_origins == [
        "http://api.local",
        "http://admin.local",
        "http://frontend.local",
    ]
    assert settings.emails_enabled is True


def test_setting_rejects_default_superuser_password_in_prod() -> None:
    with pytest.raises(ValueError, match="changethis"):
        Setting(
            ENVIRONMENT="prod",
            REDIS_HOST="localhost",
            REDIS_PORT=6379,
            MONGO_URI="mongodb://localhost:27017",
            FRONTEND_HOST="http://frontend.local",
            FIRST_SUPERUSER="admin@example.com",
            FIRST_SUPERUSER_EMAIL="admin@example.com",
            FIRST_SUPERUSER_PASSWORD="changethis",
            ALGORITHM="RS256",
            ACCESS_TOKEN_EXPIRE_MINUTES=30,
        )


