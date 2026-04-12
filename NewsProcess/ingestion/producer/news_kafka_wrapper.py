from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from ingestion.model.news_model import NewsRaw
from ingestion.producer.event_kafka_producer import EventKafkaProducer

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NewsKafkaPublisher:
    """Thin wrapper around EventKafkaProducer specific to NewsRaw events."""
    producer: EventKafkaProducer
    @classmethod
    def from_env(cls) -> "NewsKafkaPublisher":
        return cls(producer=EventKafkaProducer())

    def publish_one(self, news: NewsRaw) -> None:
        self.producer.produce_news(news)

    def publish_many(self, items: Iterable[NewsRaw], *, flush: bool = True) -> int:
        n = 0
        for it in items:
            try:
                self.publish_one(it)
                n += 1
            except Exception:
                logger.exception("Failed to publish news id=%s url=%s", getattr(it, "id", None), getattr(it, "url", None))
                raise
        if flush:
            self.producer.flush()
        return n

