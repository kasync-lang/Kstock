from __future__ import annotations

from dataclasses import dataclass, field
from os import environ
from typing import Any, Callable, Iterator, Optional

from confluent_kafka import Consumer as KafkaConsumer, KafkaError

from src.tickModel import TickModel

from logging import getLogger


logger = getLogger(__name__)


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
            "auto.offset.reset": self.auto_offset_reset,
        }
        config.update(self.extra_config)
        return config

    @staticmethod
    def from_environment() -> "ConsumerKafkaConfig":
        return ConsumerKafkaConfig(
            topic=environ.get("KAFKA_CONSUMER_TOPIC", "ohlcv-topic"),
            bootstrap_servers=environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            kafka_group_id=environ.get("KAFKA_GROUP_ID", "flink-consumer"),
            auto_offset_reset=environ.get("KAFKA_AUTO_OFFSET_RESET", "latest"),
        )

    @property
    def is_valid(self) -> bool:
        return bool(self.topic and self.bootstrap_servers and self.kafka_group_id)


class ConsumerClient:
    def __init__(
        self,
        config: ConsumerKafkaConfig,
        value_deserializer: Optional[Callable[[bytes], Any]] = None,
    ):
        if not config.is_valid:
            raise ValueError("consumer config is missing required fields")
        self.config = config
        self._value_deserializer = value_deserializer or self._default_value_deserializer
        self._consumer: Any = KafkaConsumer(config.to_confluent_config())
        self._consumer.subscribe([config.topic])

    @staticmethod
    def _default_value_deserializer(payload: bytes) -> Any:
        try:
            return TickModel.from_json(payload)
        except Exception:
            text = payload.decode("utf-8", errors="replace")
            logger.debug("falling back to raw string payload: %s", text)
            return text

    def poll(self, timeout: float = 1.0):
        message: Any = self._consumer.poll(timeout)
        if message is None:
            return None
        error = message.error()
        if error is not None:
            if error.code() == KafkaError._PARTITION_EOF:
                return None
            raise RuntimeError(str(error))

        timestamp = None
        if message.timestamp() is not None:
            timestamp = message.timestamp()[1]

        raw_key = message.key()
        if raw_key is None:
            decoded_key = None
        else:
            try:
                decoded_key = raw_key.decode("utf-8")
            except Exception:
                decoded_key = raw_key.decode("utf-8", errors="replace")

        return {
            "topic": message.topic(),
            "partition": message.partition(),
            "offset": message.offset(),
            "key": decoded_key,
            "value": self._deserialize_value(message.value()),
            "timestamp": timestamp,
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

    def stream(self, timeout: float = 1.0) -> Iterator[dict[str, Any]]:
        while True:
            item = self.poll(timeout)
            if item is not None:
                yield item

    def _deserialize_value(self, payload: bytes):
        value = self._value_deserializer(payload)
        if isinstance(value, TickModel):
            return value
        if isinstance(value, dict):
            try:
                return TickModel.from_dict(value)
            except Exception:
                logger.exception("failed to coerce mapping into TickModel")
                return value
        return value


    def close(self) -> None:
        self._consumer.close()

    def __enter__(self) -> "ConsumerClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
