
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Iterable
from confluent_kafka import KafkaException, Producer
from dotenv import load_dotenv
from ingestion.model.news_model import NewsRaw


@dataclass(frozen=True, slots=True)
class KafkaProducerConfig:
	bootstrap_servers: str
	topic: str
	client_id: str = "newsprocess"
	acks: str = "all"
	compression_type: str = "snappy"
	linger_ms: int = 25
	batch_num_messages: int = 10000
	message_timeout_ms: int = 300000
	enable_idempotence: bool = False

	@staticmethod
	def from_env(prefix: str = "KAFKA_") -> "KafkaProducerConfig":
		# Load .env if present; safe in production too.
		load_dotenv(override=False)
		bs = os.getenv(f"{prefix}BOOTSTRAP_SERVERS") or os.getenv("KAFKA_BOOTSTRAP_SERVERS")
		topic = (
			os.getenv(f"{prefix}TOPIC_NEWS_RAW")
			or os.getenv("KAFKA_TOPIC_NEWS_RAW")
			or os.getenv(f"{prefix}TOPIC")
			or os.getenv("KAFKA_TOPIC")
		)
		if not bs:
			raise ValueError("Missing Kafka bootstrap servers env var: KAFKA_BOOTSTRAP_SERVERS")
		if not topic:
			raise ValueError("Missing Kafka topic env var: KAFKA_TOPIC_NEWS_RAW (or KAFKA_TOPIC)")

		return KafkaProducerConfig(
			bootstrap_servers=bs,
			topic=topic,
			client_id=os.getenv(f"{prefix}CLIENT_ID", "newsprocess"),
			acks=os.getenv(f"{prefix}ACKS", "all"),
			compression_type=os.getenv(f"{prefix}COMPRESSION", "snappy"),
			linger_ms=int(os.getenv(f"{prefix}LINGER_MS", "25")),
			batch_num_messages=int(os.getenv(f"{prefix}BATCH_NUM_MESSAGES", "10000")),
			message_timeout_ms=int(os.getenv(f"{prefix}MESSAGE_TIMEOUT_MS", "300000")),
			enable_idempotence=os.getenv(f"{prefix}ENABLE_IDEMPOTENCE", "false").lower() in {"1", "true", "yes"},
		)

	def to_confluent_dict(self) -> dict[str, Any]:
		cfg: dict[str, Any] = {
			"bootstrap.servers": self.bootstrap_servers,
			"client.id": self.client_id,
			"acks": self.acks,
			"compression.type": self.compression_type,
			"linger.ms": self.linger_ms,
			"batch.num.messages": self.batch_num_messages,
			"message.timeout.ms": self.message_timeout_ms,
			"enable.idempotence": self.enable_idempotence,
		}
		# Remove None values (future-proofing)
		return {k: v for k, v in cfg.items() if v is not None}


class EventKafkaProducer:
	def __init__(
		self,
		config: KafkaProducerConfig | None = None,
		*,
		extra_confluent_config: dict[str, Any] | None = None,
	) -> None:
		self._config = config or KafkaProducerConfig.from_env()
		confluent_cfg = self._config.to_confluent_dict()
		if extra_confluent_config:
			confluent_cfg.update(extra_confluent_config)
		self._producer = Producer(confluent_cfg)
		self._delivery_errors: list[Exception] = []

	@property
	def topic(self) -> str:
		return self._config.topic

	def _on_delivery(self, err, msg) -> None:  # confluent-kafka callback signature
		if err is not None:
			self._delivery_errors.append(KafkaException(err))

	def produce(
		self,
		*,
		topic: str,
		key: str | bytes | None,
		value: bytes,
		headers: dict[str, str] | Iterable[tuple[str, str]] | None = None,
		max_retries: int = 10,
		retry_backoff_s: float = 0.2,
	) -> None:
		"""Produce a message with bounded retries when the local queue is full."""

		# Drive callbacks; important for delivery reports.
		self._producer.poll(0)

		attempt = 0
		while True:
			try:
				self._producer.produce(
					topic=topic,
					key=key,
					value=value,
					headers=headers,
					on_delivery=self._on_delivery,
				)
				return
			except BufferError:
				attempt += 1
				if attempt > max_retries:
					raise
				# Let producer send queued messages then retry.
				self._producer.poll(0.5)
				time.sleep(retry_backoff_s)

	def produce_news(
		self,
		news: NewsRaw,
		*,
		topic: str | None = None,
		key: str | None = None,
		headers: dict[str, str] | None = None,
	) -> None:
		"""Publish a NewsRaw event as JSON to Kafka."""

		t = topic or self._config.topic
		k = key or news.id
		base_headers = {
			"event_type": "news.raw",
			"content_type": "application/json",
		}
		if headers:
			base_headers.update(headers)

		self.produce(topic=t, key=k, value=news.to_json_bytes(), headers=base_headers)

	def flush(self, timeout_s: float = 10.0, *, raise_on_delivery_error: bool = True) -> None:
		remaining = self._producer.flush(timeout=timeout_s)
		if remaining:
			raise TimeoutError(f"Kafka producer flush timed out; {remaining} message(s) still queued")
		if raise_on_delivery_error and self._delivery_errors:
			# surface the first error; keep the rest for debugging
			raise self._delivery_errors[0]

	def close(self, timeout_s: float = 10.0) -> None:
		# confluent-kafka Producer doesn't have close(); flush is enough.
		self.flush(timeout_s=timeout_s, raise_on_delivery_error=True)


