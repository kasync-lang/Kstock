from __future__ import annotations

import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import HTTPException, Response, status
from starlette.responses import Response as StarletteResponse

from app.core.config import settings

logger = logging.getLogger(__name__)


def hash_refresh_token(token: str) -> str:
    """
    Computes SHA-256 hash of the opaque refresh token.
    Only token hashes are stored in Redis to protect against database exposure.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    """
    Generates a cryptographically secure random opaque token.
    """
    return secrets.token_urlsafe(32)


def get_cleared_cookie_headers() -> dict[str, str]:
    """
    Returns Set-Cookie header dictionary to clear the refresh token cookie
    even when an HTTPException is raised.
    """
    dummy = StarletteResponse()
    dummy.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
    )
    return dict(dummy.headers)


def set_refresh_token_cookie(response: Response, refresh_token: str) -> None:
    """
    Sets the HttpOnly refresh token cookie on the response.
    """
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
        max_age=max_age,
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
    )


def clear_refresh_token_cookie(response: Response) -> None:
    """
    Deletes the refresh token cookie from the response.
    """
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
    )


async def create_refresh_session(
    redis: Any,
    user_id: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, str]:
    """
    Creates a new session in Redis, hashes and stores the opaque refresh token.
    Returns (session_id, raw_refresh_token).
    """
    session_id = str(uuid.uuid4())
    raw_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_token)
    ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    now_iso = datetime.now(timezone.utc).isoformat()
    expires_at_iso = (
        datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    ).isoformat()

    session_data = {
        "session_id": session_id,
        "user_id": str(user_id),
        "current_token_hash": token_hash,
        "revoked": False,
        "created_at": now_iso,
        "updated_at": now_iso,
        "expires_at": expires_at_iso,
        "user_agent": user_agent,
        "ip": ip,
    }

    token_data = {
        "session_id": session_id,
        "user_id": str(user_id),
        "status": "active",
        "created_at": now_iso,
        "rotated_at": None,
    }

    await redis.set(f"session:{session_id}", json.dumps(session_data), ex=ttl_seconds)
    await redis.set(f"refresh_token:{token_hash}", json.dumps(token_data), ex=ttl_seconds)

    return session_id, raw_token


async def get_session(redis: Any, session_id: str) -> dict[str, Any] | None:
    """
    Retrieves session metadata from Redis by session_id.
    """
    session_raw = await redis.get(f"session:{session_id}")
    if not session_raw:
        return None
    try:
        return json.loads(session_raw)
    except Exception:
        return None


async def revoke_session(redis: Any, session_id: str) -> None:
    """
    Revokes the session and deletes its active refresh token record.
    Marks the session revoked=True in Redis.
    """
    session_raw = await redis.get(f"session:{session_id}")
    if not session_raw:
        return

    try:
        session_data = json.loads(session_raw)
    except Exception:
        session_data = {}

    current_hash = session_data.get("current_token_hash")
    if current_hash:
        await redis.delete(f"refresh_token:{current_hash}")

    session_data["revoked"] = True
    session_data["revoked_at"] = datetime.now(timezone.utc).isoformat()

    ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    await redis.set(f"session:{session_id}", json.dumps(session_data), ex=ttl_seconds)


async def rotate_refresh_token(
    redis: Any,
    raw_refresh_token: str,
) -> tuple[str, str, str]:
    """
    Validates the refresh token, performs rotation, and detects reuse.
    Returns (user_id, session_id, new_raw_refresh_token).

    If the presented token was previously rotated (Token Reuse Detection):
    - Entire session is revoked immediately.
    - An HTTP 401 Unauthorized exception is raised.
    """
    token_hash = hash_refresh_token(raw_refresh_token)
    token_raw = await redis.get(f"refresh_token:{token_hash}")

    if not token_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers=get_cleared_cookie_headers(),
        )

    try:
        token_data = json.loads(token_raw)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Corrupted token data",
            headers=get_cleared_cookie_headers(),
        )

    session_id = token_data.get("session_id")
    user_id = token_data.get("user_id")
    token_status = token_data.get("status", "active")

    # TOKEN REUSE DETECTION
    if token_status == "rotated":
        logger.warning(
            "Security breach detected: Rotated refresh token reuse for session %s, user %s",
            session_id,
            user_id,
        )
        if session_id:
            await revoke_session(redis, session_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected. Session has been revoked.",
            headers=get_cleared_cookie_headers(),
        )

    if token_status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token status",
            headers=get_cleared_cookie_headers(),
        )

    session_raw = await redis.get(f"session:{session_id}")
    if not session_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or not found",
            headers=get_cleared_cookie_headers(),
        )

    try:
        session_data = json.loads(session_raw)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Corrupted session data",
            headers=get_cleared_cookie_headers(),
        )

    if session_data.get("revoked", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked",
            headers=get_cleared_cookie_headers(),
        )

    if session_data.get("current_token_hash") != token_hash:
        logger.warning("Token hash mismatch with active session for session %s", session_id)
        await revoke_session(redis, session_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token mismatch. Session has been revoked.",
            headers=get_cleared_cookie_headers(),
        )

    # SUCCESSFUL ROTATION
    ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Mark current token as rotated
    token_data["status"] = "rotated"
    token_data["rotated_at"] = now_iso
    await redis.set(f"refresh_token:{token_hash}", json.dumps(token_data), ex=ttl_seconds)

    # 2. Generate new opaque token & hash
    new_raw_token = generate_refresh_token()
    new_token_hash = hash_refresh_token(new_raw_token)

    # 3. Store new token
    new_token_data = {
        "session_id": session_id,
        "user_id": user_id,
        "status": "active",
        "created_at": now_iso,
        "rotated_at": None,
    }
    await redis.set(f"refresh_token:{new_token_hash}", json.dumps(new_token_data), ex=ttl_seconds)

    # 4. Update session
    session_data["current_token_hash"] = new_token_hash
    session_data["updated_at"] = now_iso
    await redis.set(f"session:{session_id}", json.dumps(session_data), ex=ttl_seconds)

    return user_id, session_id, new_raw_token
