import logging
from collections.abc import Mapping
from threading import Lock
from typing import Any


from src.tickModel import TickModel, Candle

logger = logging.getLogger(__name__)

TIMEFRAME_MS = 60_000          # 1m
ALLOWED_LATENESS_MS = 10_000  # 10s


class OHLCVAggregator:
    def __init__(self, timeframe: int = TIMEFRAME_MS, allowed_lateness_ms: int = ALLOWED_LATENESS_MS):
        if timeframe <= 0:
            raise ValueError("timeframe must be positive")
        if allowed_lateness_ms < 0:
            raise ValueError("allowed lateness must be non-negative")
        self.candles: dict[Any, Candle] = {}
        self.max_event_ts = 0
        self.time_frame_ms = timeframe
        self.allowed_lateness_ms = allowed_lateness_ms
        self._lock = Lock()

    def get_bucket_stats(self, ts_ms: int) -> int:
        return (ts_ms//self.time_frame_ms) * self.time_frame_ms

    def process_tick(self, tick: TickModel | Mapping[str, Any]) -> bool:
        if not isinstance(tick, TickModel):
            tick = TickModel.from_dict(tick)
        with self._lock:
            symbol = tick.symbol
            price = tick.price
            volume = tick.volume
            ts = tick.ts
            if ts < self.get_watermark():
                logger.debug("dropping late tick for %s at ts=%s", symbol, ts)
                return False
            self.max_event_ts = max(self.max_event_ts, ts)
            bucket_start = self.get_bucket_stats(ts)
            key = (symbol, bucket_start)
            candle = self.candles.get(key)
            if candle is None:
                self.candles[key] = Candle(
                    symbol=symbol, bucket_start=bucket_start, open=price, high=price, low=price,
                    close=price, volume=volume, first_ts=ts, last_ts=ts, trade_count=1,
                )
                return True

            candle.high = max(candle.high, price)
            candle.low = min(candle.low, price)
            candle.trade_count += 1
            if ts < candle.first_ts:
                candle.first_ts = ts
                candle.open = price
            elif ts >= candle.last_ts:
                candle.last_ts = ts
                candle.close = price
            candle.volume += volume
            return True

    def get_watermark(self) -> int:
        return self.max_event_ts - self.allowed_lateness_ms

    def flush_finalized(self) -> list[Candle]:
        finalized = self.peek_finalized()
        self.acknowledge(finalized)
        return finalized

    def peek_finalized(self) -> list[Candle]:
        with self._lock:
            watermark = self.get_watermark()
            finalized = [
                candle
                for candle in self.candles.values()
                if candle.bucket_start + self.time_frame_ms <= watermark
            ]
            finalized.sort(key=lambda candle: (candle.bucket_start, candle.symbol, candle.first_ts))
            return finalized

    def acknowledge(self, finalized: list[Candle]) -> None:
        with self._lock:
            for candle in finalized:
                key = (candle.symbol, candle.bucket_start)
                if self.candles.get(key) is candle:
                    del self.candles[key]

    def peek_all(self) -> list[Candle]:
        with self._lock:
            candles = list(self.candles.values())
            candles.sort(key=lambda candle: (candle.bucket_start, candle.symbol, candle.first_ts))
            return candles

    def flush_all(self) -> list[Candle]:
        with self._lock:
            finalized = list(self.candles.values())
            self.candles.clear()
            finalized.sort(key=lambda candle: (candle.bucket_start, candle.symbol, candle.first_ts))
            return finalized

