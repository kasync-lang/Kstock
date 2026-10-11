from __future__ import annotations

import pytest

from app import utils
from app.core.config import settings


class DummySMTP:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.started_tls = False
        self.logged_in: tuple[str, str] | None = None
        self.sent: tuple[str, list[str], str] | None = None
        self.quit_called = False

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.logged_in = (username, password)

    def sendmail(self, from_email: str, recipients: list[str], message: str) -> None:
        self.sent = (from_email, recipients, message)

    def quit(self) -> None:
        self.quit_called = True


class FailingSMTP(DummySMTP):
    def sendmail(self, from_email: str, recipients: list[str], message: str) -> None:
        self.sent = (from_email, recipients, message)
        raise RuntimeError("send failed")


def _configure_email_settings(monkeypatch: pytest.MonkeyPatch, *, smtp_ssl: bool = False) -> None:
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USER", "mailer")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "secret")
    monkeypatch.setattr(settings, "SMTP_TLS", not smtp_ssl)
    monkeypatch.setattr(settings, "SMTP_SSL", smtp_ssl)
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setattr(settings, "EMAILS_FROM_NAME", "noreply@example.com")
    monkeypatch.setattr(settings, "PROJECT_NAME", "Auth Test")
    monkeypatch.setattr(settings, "FRONTEND_HOST", "http://frontend.local")
    monkeypatch.setattr(settings, "PREFIX_API", "/api")
    monkeypatch.setattr(settings, "EMAIL_RESET_TOKEN_EXPIRE_HOURS", 1)
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30)


def test_render_email_template_renders_context() -> None:
    html = utils.render_email_template(
        template_name="test_email.html",
        context={"project_name": "Auth Test", "email_to": "user@example.com"},
    )

    assert html.strip()
    assert "<!doctype html" in html.lower()


def test_generate_test_email_builds_subject_and_html(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_email_settings(monkeypatch)

    email = utils.generate_test_email("user@example.com")

    assert email.subject == "Auth Test test"
    assert email.html_content.strip()
    assert "<!doctype html" in email.html_content.lower()


def test_generate_reset_password_email_contains_reset_link(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_email_settings(monkeypatch)

    email = utils.generate_reset_password_email(
        email_to="user@example.com",
        email="user@example.com",
        token="reset-token",
    )

    assert "Password recovery" in email.subject
    assert "reset-password?token=reset-token" in email.html_content


def test_generate_signup_verify_email_contains_verify_link(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_email_settings(monkeypatch)

    email = utils.generate_signup_verify_email(email="user@example.com", token="verify-token")

    assert "Signup verification" in email.subject
    assert "/api/signup-verify?token=verify-token" in email.html_content


def test_generate_new_account_email_contains_password(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_email_settings(monkeypatch)

    email = utils.generate_new_account_email(
        email_to="user@example.com",
        username="user@example.com",
        password="StrongPass1!",
    )

    assert "New account" in email.subject
    assert "StrongPass1!" in email.html_content


def test_send_email_uses_smtp_with_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_email_settings(monkeypatch, smtp_ssl=False)
    smtp_instance = DummySMTP("smtp.example.com", 587)
    monkeypatch.setattr(utils.smtplib, "SMTP", lambda host, port: smtp_instance)

    utils.send_email(
        email_to="user@example.com",
        subject="Hello",
        html_content="<b>Hello</b>",
    )

    assert smtp_instance.started_tls is True
    assert smtp_instance.logged_in == ("mailer", "secret")
    assert smtp_instance.sent is not None
    assert smtp_instance.quit_called is True


def test_send_email_uses_smtp_ssl(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_email_settings(monkeypatch, smtp_ssl=True)
    smtp_instance = DummySMTP("smtp.example.com", 587)
    monkeypatch.setattr(utils.smtplib, "SMTP_SSL", lambda host, port: smtp_instance)

    utils.send_email(
        email_to="user@example.com",
        subject="Hello",
        html_content="<b>Hello</b>",
    )

    assert smtp_instance.started_tls is False
    assert smtp_instance.sent is not None
    assert smtp_instance.quit_called is True


def test_send_email_re_raises_and_closes_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_email_settings(monkeypatch, smtp_ssl=False)
    smtp_instance = FailingSMTP("smtp.example.com", 587)
    monkeypatch.setattr(utils.smtplib, "SMTP", lambda host, port: smtp_instance)

    with pytest.raises(RuntimeError, match="send failed"):
        utils.send_email(
            email_to="user@example.com",
            subject="Hello",
            html_content="<b>Hello</b>",
        )

    assert smtp_instance.quit_called is True


def test_password_reset_token_roundtrip_returns_email() -> None:
    token = utils.generate_password_reset_token("user@example.com")

    assert utils.verify_password_reset_token(token) == "user@example.com"


def test_verify_password_reset_token_returns_none_for_invalid_token() -> None:
    assert utils.verify_password_reset_token("not-a-valid-token") is None



