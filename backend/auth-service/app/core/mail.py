"""Hands emails to mail-service by publishing to the email_requests Kafka topic.

auth-service never renders or sends mail itself: it names a template owned by
mail-service (backend/mail-service/templates) and passes that template's data.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from aiokafka import AIOKafkaProducer

from app.core.config import settings

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer | None = None
_lock = asyncio.Lock()


async def _get_producer() -> AIOKafkaProducer:
    # Started lazily so auth-service still boots (and logs users in) while Kafka
    # is down; the next email retries the connection.
    global _producer
    async with _lock:
        if _producer is None:
            producer = AIOKafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                acks="all",
                key_serializer=lambda k: k.encode(),
                value_serializer=lambda v: json.dumps(v).encode(),
            )
            await producer.start()
            _producer = producer
        return _producer


async def start() -> None:
    try:
        await _get_producer()
    except Exception as e:
        logger.error("Kafka producer for emails not started, will retry on first email: %s", e)


async def stop() -> None:
    global _producer
    async with _lock:
        if _producer is not None:
            await _producer.stop()
            _producer = None


async def send_email(*, template: str, to: str, data: dict[str, Any]) -> None:
    """Queue one email. Returns once Kafka has acked it; mail-service sends it."""
    producer = await _get_producer()
    request = {
        "id": str(uuid.uuid4()),
        "template": template,
        "to": to,
        "data": data,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await producer.send_and_wait(settings.KAFKA_EMAIL_TOPIC, key=to, value=request)
    logger.info("Email queued id=%s template=%s to=%s", request["id"], template, to)
