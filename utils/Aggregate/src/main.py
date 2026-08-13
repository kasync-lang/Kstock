from __future__ import annotations

import asyncio
import logging
import os
import threading
from contextlib import suppress
from datetime import UTC, datetime
from typing import Protocol
from src.clickhouse_client import build_clickhouse_client
from dotenv import load_dotenv

from src.aggregator import OHLCVAggregator
from src.consumer import ConsumerClient, ConsumerKafkaConfig


logger = logging.getLogger(__name__)


class CandleWriter(Protocol):
    def insert(self, table: str, data: list[list[object]], column_names: list[str]) -> None: ...

# This service owns only sub-day aggregation. Daily and weekly candles are
# produced by the downstream service from the 1d data set.
TABLES_BY_TIMEFRAME = {
    60_000: "ohlcv_1m",
    5 * 60_000: "ohlcv_5m",
    15 * 60_000: "ohlcv_15m",
    60 * 60_000: "ohlcv_1h",
}

TIMEFRAMES = [60_000, 5 * 60_000, 15 * 60_000, 60 * 60_000]

load_dotenv()

FLUSH_INTERVAL_SECONDS = float(os.getenv("FLUSH_INTERVAL_SECONDS", "5"))
KAFKA_POLL_TIMEOUT_SECONDS = float(os.getenv("KAFKA_POLL_TIMEOUT_SECONDS", "1.0"))


def build_aggregators() -> list[OHLCVAggregator]:
    return [OHLCVAggregator(timeframe=time_frame) for time_frame in TIMEFRAMES]





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
    clickhouse_client: CandleWriter,
    *,
    drain: bool = False,
) -> int:
    inserted = 0
    for agg in aggs:
        finalized = agg.peek_all() if drain else agg.peek_finalized()
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
                column_names=["symbol", "timestamp", "open", "high", "low", "close", "volume"],
            )
            agg.acknowledge(finalized)
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
                print(item)
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
