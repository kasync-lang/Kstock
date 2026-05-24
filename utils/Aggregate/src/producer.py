from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import os
from confluent_kafka import Producer as KafkaProducer

from src.tickModel import TickModel


@dataclass
class ProducerKafkaConfig:
    bootstrap_servers: str
    topic: str = "ohlcv-topic"
    client_id: str = "flink-producer"
    acks: str = "all"
    linger_ms: int = 0
    queue_buffering_max_messages: int = 100_000
    extra_config: dict[str, Any] = field(default_factory=dict)

    def to_confluent_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {
            "bootstrap.servers": self.bootstrap_servers,
            "client.id": self.client_id,
            "acks": self.acks,
            "linger.ms": self.linger_ms,
            "queue.buffering.max.messages": self.queue_buffering_max_messages,
        }
        config.update(self.extra_config)
        return config

    @staticmethod
    def from_env() -> "ProducerKafkaConfig":
        return ProducerKafkaConfig(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            topic=os.getenv("KAFKA_TOPIC", "ohlcv-topic"),
        )



class ProducerClient:
    def __init__(self, config: ProducerKafkaConfig):
        self.config = config
        self._producer = KafkaProducer(config.to_confluent_config())

    def produce(
        self,
        value: bytes | str,
        key: bytes | str | None = None,
        topic: Optional[str] = None,
        headers: Optional[list[tuple[str, str]]] = None,
        on_delivery: Optional[Callable[[Any, Any], None]] = None,
    ) -> None:
        target_topic = self.config.topic if topic is None else topic
        payload = value.encode("utf-8") if isinstance(value, str) else value
        if key is None:
            self._producer.produce(
                topic=target_topic,
                value=payload,
                headers=headers,
                callback=on_delivery,
            )
        else:
            encoded_key = key.encode("utf-8") if isinstance(key, str) else key
            self._producer.produce(
                topic=target_topic,
                value=payload,
                key=encoded_key,
                headers=headers,
                callback=on_delivery,
            )
        self._producer.poll(0)

    def produce_tick(
        self,
        tick: "TickModel",
        topic: Optional[str] = None,
        on_delivery: Optional[Callable[[Any, Any], None]] = None,
    ) -> None:

        if not isinstance(tick, TickModel):
            raise TypeError("tick must be a TickModel instance")
        self.produce(
            value=tick.to_json(),
            key=tick.symbol,
            topic=topic,
            on_delivery=on_delivery,
        )

    def flush(self) -> int:
        return self._producer.flush(0)

    def close(self) -> None:
        self.flush()

    def __enter__(self) -> "ProducerClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

