from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("PRIVATE_KEY_PATH", str(REPO_ROOT))
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("FRONTEND_HOST", "http://localhost:5173")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")
os.environ.setdefault("FIRST_SUPERUSER", "admin@example.com")
os.environ.setdefault("FIRST_SUPERUSER_EMAIL", "admin@example.com")
os.environ.setdefault("FIRST_SUPERUSER_PASSWORD", "StrongPass1!")
os.environ.setdefault("ALGORITHM", "RS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")

import pytest
from beanie import PydanticObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.api.main import api_router
from app.core.config import KeyStore
from app.model.User import Oauth2Account, User
from app.schema.user import UserPublic


class InMemoryRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                count += 1
        return count

    async def getdel(self, key: str) -> str | None:
        return self.store.pop(key, None)

    async def expire(self, key: str, time: int) -> bool:
        return key in self.store

    async def exists(self, *keys: str) -> int:
        return sum(1 for k in keys if k in self.store)

    async def aclose(self) -> None:
        return None


def build_user(
    *,
    email: str = "user@example.com",
    hashed_password: str = "hashed-password",
    full_name: str = "Regular User",
    is_actived: bool = True,
    is_verified: bool = True,
    role: str = "basic_user",
    user_id: PydanticObjectId | None = None,
) -> User:
    return User.model_construct(
        id=user_id or PydanticObjectId(),
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        is_actived=is_actived,
        is_verified=is_verified,
        role=role,
    )


def build_oauth_account(
    *,
    email: str = "oauth@example.com",
    name: str = "OAuth User",
    provider: str = "google",
    provider_account_id: str = "google-123",
    scope: list[str] | None = None,
    is_actived: bool = True,
    role: str = "basic_user",
    account_id: PydanticObjectId | None = None,
) -> Oauth2Account:
    return Oauth2Account.model_construct(
        id=account_id or PydanticObjectId(),
        provider=provider,
        email=email,
        provider_account_id=provider_account_id,
        name=name,
        scope=scope or ["openid", "email", "profile"],
        is_actived=is_actived,
        role=role,
    )


def to_public_user(account: User | Oauth2Account) -> UserPublic:
    return UserPublic(
        id=str(account.id),
        email=account.email,
        full_name=getattr(account, "full_name", None) or getattr(account, "name", None),
        is_actived=account.is_actived,
        is_superuser=getattr(account, "role", "basic_user") == "admin",
        provider=getattr(account, "provider", None),
    )


@pytest.fixture(autouse=True)
def load_rsa_keys() -> None:
    KeyStore.private_key = None
    KeyStore.public_key = None
    KeyStore.load_key()


@pytest.fixture
def in_memory_redis() -> InMemoryRedis:
    return InMemoryRedis()


@pytest.fixture
def api_app(in_memory_redis: InMemoryRedis) -> FastAPI:
    app = FastAPI()
    app.include_router(api_router)
    app.state.redis = in_memory_redis
    return app


@pytest.fixture
def client(api_app: FastAPI):
    with TestClient(api_app) as test_client:
        yield test_client


@pytest.fixture
def auth_overrides(api_app: FastAPI):
    def _apply(
        *,
        public_user: UserPublic | None = None,
        account: Any | None = None,
        superuser: bool = False,
    ) -> None:
        if public_user is not None:
            api_app.dependency_overrides[deps.parse_user_db_to_currentuser] = lambda: public_user
        if account is not None:
            api_app.dependency_overrides[deps.get_current_user] = lambda: account
        if superuser:
            if public_user is None:
                raise ValueError("public_user is required when overriding superuser access")
            api_app.dependency_overrides[deps.get_current_active_superuser] = lambda: public_user

    return _apply


@pytest.fixture
def user_account() -> User:
    return build_user()


@pytest.fixture
def inactive_user_account() -> User:
    return build_user(email="inactive@example.com", is_actived=False)


@pytest.fixture
def unverified_user_account() -> User:
    return build_user(email="unverified@example.com", is_verified=False)


@pytest.fixture
def superuser_account() -> User:
    return build_user(email="admin@example.com", role="admin", full_name="Admin User")


@pytest.fixture
def oauth_account() -> Oauth2Account:
    return build_oauth_account()


@pytest.fixture
def user_public(user_account: User) -> UserPublic:
    return to_public_user(user_account)


@pytest.fixture
def inactive_user_public(inactive_user_account: User) -> UserPublic:
    return to_public_user(inactive_user_account)


@pytest.fixture
def superuser_public(superuser_account: User) -> UserPublic:
    return to_public_user(superuser_account)


@pytest.fixture
def oauth_public(oauth_account: Oauth2Account) -> UserPublic:
    return to_public_user(oauth_account)
