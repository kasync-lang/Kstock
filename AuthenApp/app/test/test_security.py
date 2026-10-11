from __future__ import annotations

import hashlib
from datetime import timedelta

import jwt

from app.core import security
from app.core.config import KeyStore, settings


def test_create_access_token_embeds_subject() -> None:
    token = security.create_access_token(subject="subject-123", expires_delta=timedelta(minutes=5))

    payload = jwt.decode(token, KeyStore.public_key, algorithms=[settings.ALGORITHM])

    assert payload["sub"] == "subject-123"
    assert "exp" in payload


def test_get_password_hash_and_verify_password_roundtrip() -> None:
    password = "StrongPass1!"

    hashed_password = security.get_password_hash(password)

    assert hashed_password != password
    assert security.verify_password(password, hashed_password) is True
    assert security.verify_password("WrongPass1!", hashed_password) is False


def test_is_strong_password_accepts_valid_password() -> None:
    assert security.is_strong_password("StrongPass1!") is True


def test_is_strong_password_rejects_weak_password() -> None:
    assert security.is_strong_password("weakpass") is False


def test_hash_token_produces_sha256() -> None:
    raw_token = "some-random-opaque-token"
    expected = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    assert security.hash_token(raw_token) == expected


def test_generate_opaque_token_returns_unique_strings() -> None:
    token1 = security.generate_opaque_token()
    token2 = security.generate_opaque_token()
    assert isinstance(token1, str)
    assert len(token1) >= 32
    assert token1 != token2
