from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from ingestion.model.news_model import NewsRaw
from ingestion.producer.news_kafka_wrapper import NewsKafkaPublisher
from ingestion.source.api_ingester import APIGeter, load_symbols


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Fetch news and publish to Kafka.")
    parser.add_argument("--from-date", type=_parse_date, default=date.today() - timedelta(days=1), help="Start date (inclusive) in YYYY-MM-DD format")
    parser.add_argument("--to-date", type=_parse_date, default=date.today(), help="End date (inclusive) in YYYY-MM-DD format")
    args = parser.parse_args()

    symbols = load_symbols()
    if not symbols:
        logger.warning("No symbols loaded. Exiting.")
        return

    api_getter = APIGeter()
    publisher = NewsKafkaPublisher.from_env()

    logger.info("Fetching news for %d symbols from %s to %s", len(symbols), args.from_date, args.to_date)
    all_news: list[NewsRaw] = []
    for s in symbols:
        try:
            news_items = api_getter.fetch_news_raw(s, from_date=args.from_date, to_date=args.to_date)
            all_news.extend(news_items)
            logger.info("Fetched %d news items for symbol %s", len(news_items), s)
        except Exception:
            logger.exception("Failed to fetch news for symbol %s", s)

    if not all_news:
        logger.info("No news items fetched. Exiting.")
        return

    logger.info("Publishing %d news items to Kafka topic %s", len(all_news), publisher.producer.topic)
    try:
        n_published = publisher.publish_many(all_news)
        logger.info("Successfully published %d news items", n_published)
    except Exception:
        logger.exception("Failed to publish news items to Kafka")


if __name__ == "__main__":
    main()