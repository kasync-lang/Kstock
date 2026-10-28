from __future__ import annotations

from typing import Any

import pytest

from app.core import mail
from app.core.config import settings

# conftest replaces mail.send_email with a recorder; this file tests the real one.
real_send_email = mail.send_email


class FakeProducer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, dict[str, Any]]] = []

    async def send_and_wait(self, topic: str, *, key: str, value: dict[str, Any]) -> None:
        self.sent.append((topic, key, value))


@pytest.mark.asyncio
async def test_send_email_publishes_request_keyed_by_recipient(monkeypatch: pytest.MonkeyPatch) -> None:
    producer = FakeProducer()

    async def fake_get_producer() -> FakeProducer:
        return producer

    monkeypatch.setattr(mail, "_get_producer", fake_get_producer)

    await real_send_email(template="reset_password", to="user@example.com", data={"link": "http://x"})

    assert len(producer.sent) == 1
    topic, key, value = producer.sent[0]
    assert topic == settings.KAFKA_EMAIL_TOPIC
    assert key == "user@example.com"
    assert value["template"] == "reset_password"
    assert value["to"] == "user@example.com"
    assert value["data"] == {"link": "http://x"}
    assert value["id"] and value["created_at"]


@pytest.mark.asyncio
async def test_start_does_not_raise_when_kafka_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_get_producer() -> None:
        raise ConnectionError("kafka down")

    monkeypatch.setattr(mail, "_get_producer", failing_get_producer)

    await mail.start()
