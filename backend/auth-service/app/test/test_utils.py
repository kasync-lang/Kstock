from __future__ import annotations

import pytest

from app import utils


def test_password_reset_token_roundtrip_returns_email() -> None:
    token = utils.generate_password_reset_token("user@example.com")

    assert utils.verify_password_reset_token(token) == "user@example.com"


def test_verify_password_reset_token_returns_none_for_invalid_token() -> None:
    assert utils.verify_password_reset_token("not-a-valid-token") is None



