from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from os import environ

from confluent_kafka import Consumer as KafkaConsumer

from src.tickModel import TickModel


@dataclass
class ConsumerKafkaConfig:
    topic: str
    bootstrap_servers: str
    kafka_group_id: str
    auto_commit: bool = True
    auto_offset_reset: str = "latest"
    extra_config: dict[str, Any] = field(default_factory=dict)

    def to_confluent_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.kafka_group_id,
            "enable.auto.commit": self.auto_commit,
            "auto.offset.reset": "earliest",
        }
        config.update(self.extra_config)
        return config
    @staticmethod
    def from_environment():
        return ConsumerKafkaConfig(
            topic=environ.get("KAFKA_CONSUMER_TOPIC", "ohlcv-topic"),
            bootstrap_servers=environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            kafka_group_id=environ.get("KAFKA_GROUP_ID", "flink-consumer"),
            auto_offset_reset="earliest",

        )

class ConsumerClient:
    def __init__(
        self,
        config: ConsumerKafkaConfig,
        value_deserializer: Optional[Callable[[bytes], Any]] = None,
    ):
        self.config = config
        self._value_deserializer = value_deserializer or self._default_value_deserializer
        self._consumer = KafkaConsumer(config.to_confluent_config())
        self._consumer.subscribe([config.topic])

    @staticmethod
    def _default_value_deserializer(payload: bytes) -> Any:
        text = payload.decode("utf-8")
        try:
            import json

            return json.loads(text)
        except Exception:
            return text

    def poll(self, timeout: float = 1.0):
        message = self._consumer.poll(timeout)
        if message is None:
            print(f"No message at consumer line64: {message}")
            return None
        if message.error():
            raise RuntimeError(message.error())
        return {
            "topic": message.topic(),
            "partition": message.partition(),
            "offset": message.offset(),
            "key": message.key().decode("utf-8") if message.key() else None,
            "value": self._deserialize_value(message.value()),
            "timestamp": message.timestamp()[1],
            "headers": message.headers(),
        }

    def consume(self, max_messages: int = 1, timeout: float = 1.0) -> list[Any]:
        messages = []
        for _ in range(max_messages):
            item = self.poll(timeout)
            if item is None:
                break
            messages.append(item)
        return messages

    async def stream(self, timeout: float = 1.0):
        while True:
            item = self.poll(timeout)
            if item is not None:
                yield item

    def _deserialize_value(self, payload: bytes):
        value = self._value_deserializer(payload)


        return TickModel.from_dict(value)


    def close(self) -> None:
        self._consumer.close()

    def __enter__(self) -> "ConsumerClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
