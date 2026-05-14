import datetime
from datetime import timezone, datetime
from enum import Enum


from src.tickModel import TickModel, Candle
from typing import Dict, Any
TIMEFRAME_MS = 60_000          # 1m
ALLOWED_LATENESS_MS = 10_000  # 10s
class OHLCVAggregator:
    def __init__(self, timeframe: int = TIMEFRAME_MS):
        self.candles:dict[Any,Candle] = {}
        self.max_event_ts = 0
        self.time_frame_ms = timeframe
    def get_bucket_stats(self, ts_ms:int):
        return (ts_ms//self.time_frame_ms) * self.time_frame_ms
    def process_tick(self, tick:TickModel):
        symbol = tick.symbol
        price = tick.price
        volume = tick.volume
        ts = tick.ts
        if ts < self.get_watermark():
            return
        self.max_event_ts = max(self.max_event_ts, ts)
        bucket_stats = self.get_bucket_stats(ts)
        key = (symbol, bucket_stats)
        candle = self.candles.get(key)
        if candle is None:
            self.candles[key] = Candle(
                symbol=symbol,
                bucket_start=bucket_stats,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
                first_ts=ts,
                last_ts=ts

            )
            return


        candle.high = max(candle.high, price)
        candle.low = min(candle.low, price)
        if ts <candle.first_ts:
            candle.first_ts = ts
            candle.open = price
        elif ts > candle.last_ts:
            candle.last_ts = ts
            candle.close = price
        candle.volume += volume
    def get_watermark(self):
        return self.max_event_ts - ALLOWED_LATENESS_MS

    #finalize candles that are older than watermark
    def flush_finalized(self):
        watermark = self.get_watermark()
        print("watermark is: ", watermark)
        finalized = []
        for key, candle in list(self.candles.items()):
            bucket_end = candle.bucket_start + self.time_frame_ms
            if bucket_end <= watermark:
                finalized.append(candle)
                del self.candles[key]
        return finalized

# agg = OHLCVAggregator()
# ticks = []
# for tick in ticks:
#     agg.process_tick(tick)
# finalized_candles = agg.flush_finalized()
# for candle in finalized_candles:
#     dt = datetime.fromtimestamp(candle.bucket_start/1000, tz=timezone.utc)
#     print(candle)

