from __future__ import annotations

import asyncio
import logging
import os
import threading
from contextlib import suppress
from datetime import UTC, datetime

import clickhouse_connect
from dotenv import load_dotenv

from src.aggregator import OHLCVAggregator
from src.consumer import ConsumerClient, ConsumerKafkaConfig


logger = logging.getLogger(__name__)

TABLES_BY_TIMEFRAME = {
    60_000: "ohlcv_1m",
    5 * 60_000: "ohlcv_5m",
    15 * 60_000: "ohlcv_15m",
    60 * 60_000: "ohlcv_1h",
}

TIMEFRAMES = [60_000, 5 * 60_000, 15 * 60_000, 60 * 60_000]
FLUSH_INTERVAL_SECONDS = float(os.getenv("FLUSH_INTERVAL_SECONDS", "5"))
KAFKA_POLL_TIMEOUT_SECONDS = float(os.getenv("KAFKA_POLL_TIMEOUT_SECONDS", "1.0"))

load_dotenv()


def build_aggregators() -> list[OHLCVAggregator]:
    return [OHLCVAggregator(timeframe=time_frame) for time_frame in TIMEFRAMES]


def build_clickhouse_client() -> clickhouse_connect.driver.Client:
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=os.getenv("CLICKHOUSE_DB", "default"),
    )


def _candle_rows(finalized: list) -> list[list[object]]:
    return [
        [
            candle.symbol,
            datetime.fromtimestamp(candle.bucket_start / 1000, tz=UTC),
            candle.open,
            candle.high,
            candle.low,
            candle.close,
            candle.volume,
        ]
        for candle in finalized
    ]


def flush_candles(
    aggs: list[OHLCVAggregator],
    clickhouse_client: clickhouse_connect.driver.Client,
    *,
    drain: bool = False,
) -> int:
    inserted = 0
    for agg in aggs:
        finalized = agg.flush_all() if drain else agg.flush_finalized()
        if not finalized:
            continue

        table_name = TABLES_BY_TIMEFRAME.get(agg.time_frame_ms)
        if table_name is None:
            logger.warning("unknown timeframe %s; skipping %s candles", agg.time_frame_ms, len(finalized))
            continue

        batch = _candle_rows(finalized)
        if not batch:
            continue

        try:
            clickhouse_client.insert(
                table_name,
                batch,
                column_names=["symbol", "open_time", "open", "high", "low", "close", "volume"],
            )
            inserted += len(batch)
        except Exception:
            logger.exception("failed to insert %s candles into %s", len(batch), table_name)

    return inserted


def consume_loop(aggs: list[OHLCVAggregator], stop_event: threading.Event) -> None:
    consumer_config = ConsumerKafkaConfig.from_environment()
    logger.info("starting kafka consumer for topic=%s", consumer_config.topic)
    try:
        with ConsumerClient(consumer_config) as consumer:
            while not stop_event.is_set():
                item = consumer.poll(timeout=KAFKA_POLL_TIMEOUT_SECONDS)
                if item is None:
                    continue

                tick = item["value"]
                try:
                    for agg in aggs:
                        agg.process_tick(tick)
                except Exception:
                    logger.exception(
                        "failed to process message topic=%s partition=%s offset=%s",
                        item.get("topic"),
                        item.get("partition"),
                        item.get("offset"),
                    )
    except Exception:
        logger.exception("consumer loop terminated unexpectedly")
        stop_event.set()


async def main() -> None:
    aggs = build_aggregators()
    clickhouse_client = build_clickhouse_client()
    stop_event = threading.Event()
    consumer_thread = threading.Thread(target=consume_loop, args=(aggs, stop_event), daemon=True)
    consumer_thread.start()

    try:
        while True:
            flush_candles(aggs, clickhouse_client)
            await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
    finally:
        stop_event.set()
        consumer_thread.join(timeout=max(FLUSH_INTERVAL_SECONDS * 2, 5.0))
        flush_candles(aggs, clickhouse_client, drain=True)
        with suppress(Exception):
            clickhouse_client.close()


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    asyncio.run(main())
