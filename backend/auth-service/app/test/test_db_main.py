from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from app.core import db as db_module
from app.main import lifespan, root
from app.model.User import User
import app.main as main_module


class FakeCollection:
    def __init__(self, indexes: dict[str, dict] | None = None) -> None:
        self.indexes = indexes or {}
        self.dropped: list[str] = []
        self.created: list[tuple[str, bool]] = []

    async def index_information(self):
        return self.indexes

    async def drop_index(self, index_name: str) -> None:
        self.dropped.append(index_name)

    async def create_index(self, field_name: str, unique: bool = False) -> None:
        self.created.append((field_name, unique))


class FakeDatabase:
    def __init__(self, collection: FakeCollection) -> None:
        self.collection = collection

    def __getitem__(self, _name: str) -> FakeCollection:
        return self.collection


class FakeMongoClient:
    def __init__(self, uri: str, collection: FakeCollection) -> None:
        self.uri = uri
        self.collection = collection

    def __getitem__(self, _name: str) -> FakeDatabase:
        return FakeDatabase(self.collection)


class FakeRedis:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_init_db_raises_when_mongo_uri_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_module.settings, "MONGO_URI", "")

    with pytest.raises(ValueError, match="MongoDB URI not found"):
        await db_module.init_db()


@pytest.mark.asyncio
async def test_init_db_recreates_email_index_and_initializes_beanie(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_module.settings, "MONGO_URI", "mongodb://example")
    collection = FakeCollection(indexes={"email_1": {}})
    mongo_client = FakeMongoClient("mongodb://example", collection)
    init_beanie_calls: dict[str, object] = {}

    monkeypatch.setattr(db_module, "AsyncIOMotorClient", lambda uri: mongo_client)

    async def fake_init_beanie(*, database, document_models):
        init_beanie_calls["database"] = database
        init_beanie_calls["document_models"] = document_models

    monkeypatch.setattr(db_module, "init_beanie", fake_init_beanie)

    await db_module.init_db()

    assert collection.dropped == ["email_1"]
    assert collection.created == [("email", True)]
    assert init_beanie_calls["document_models"] == [db_module.User, db_module.Oauth2Account]


@pytest.mark.asyncio
async def test_lifespan_initializes_dependencies_and_closes_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    redis_instance = FakeRedis()
    load_key_called = {"value": False}
    dotenv_called = {"value": False}
    init_db_called = {"value": False}

    monkeypatch.setattr(main_module.KeyStore, "load_key", classmethod(lambda cls: load_key_called.__setitem__("value", True)))
    monkeypatch.setattr(main_module, "load_dotenv", lambda verbose=True: dotenv_called.__setitem__("value", True))

    async def fake_init_db() -> None:
        init_db_called["value"] = True

    monkeypatch.setattr(main_module, "init_db", fake_init_db)
    monkeypatch.setattr(main_module.redis, "Redis", lambda **kwargs: redis_instance)

    app = FastAPI()
    async with lifespan(app):
        assert load_key_called["value"] is True
        assert dotenv_called["value"] is True
        assert init_db_called["value"] is True
        assert app.state.redis is redis_instance

    assert redis_instance.closed is True


@pytest.mark.asyncio
async def test_root_returns_html_response() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})

    response = await root(request)

    assert response.status_code == 200
    assert b"<!doctype html>" in response.body.lower()


def test_user_update_timestamp_refreshes_updated_at(user_account: User) -> None:
    before = datetime.now(timezone.utc) - timedelta(days=1)
    user_account.updated_at = before

    user_account.update_timestamp()

    assert user_account.updated_at > before


