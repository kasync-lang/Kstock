import unittest

from src.aggregator import ALLOWED_LATENESS_MS, OHLCVAggregator
from src.tickModel import TickModel


class TickModelTests(unittest.TestCase):
    def test_from_dict_accepts_current_schema(self) -> None:
        tick = TickModel.from_dict({"ts": 1, "price": 12.5, "symbol": "AAPL", "volume": 3})
        self.assertEqual(tick.ts, 1)
        self.assertEqual(tick.price, 12.5)
        self.assertEqual(tick.symbol, "AAPL")
        self.assertEqual(tick.volume, 3)

    def test_from_dict_accepts_legacy_schema(self) -> None:
        tick = TickModel.from_dict({"t": 1, "p": 12.5, "s": "AAPL", "v": 3})
        self.assertEqual(tick.to_dict(), {"ts": 1, "price": 12.5, "symbol": "AAPL", "volume": 3})

    def test_json_round_trip(self) -> None:
        original = TickModel(ts=42, price=100.1, symbol="MSFT", volume=7)
        restored = TickModel.from_json(original.to_json())
        self.assertEqual(restored, original)


class AggregatorTests(unittest.TestCase):
    def test_process_tick_updates_ohlcv_and_trade_count(self) -> None:
        agg = OHLCVAggregator()
        agg.process_tick(TickModel(ts=1_000_050, price=101.0, symbol="AAPL", volume=5))
        agg.process_tick(TickModel(ts=1_000_000, price=100.0, symbol="AAPL", volume=2))

        candles = list(agg.candles.values())
        self.assertEqual(len(candles), 1)
        candle = candles[0]

        self.assertEqual(candle.open, 100.0)
        self.assertEqual(candle.high, 101.0)
        self.assertEqual(candle.low, 100.0)
        self.assertEqual(candle.close, 101.0)
        self.assertEqual(candle.volume, 7)
        self.assertEqual(candle.trade_count, 2)

    def test_late_event_is_dropped(self) -> None:
        agg = OHLCVAggregator()
        fresh = TickModel(ts=1_000_000, price=100.0, symbol="AAPL", volume=1)
        agg.process_tick(fresh)

        late_ts = fresh.ts - ALLOWED_LATENESS_MS - 1
        late = TickModel(ts=late_ts, price=99.0, symbol="AAPL", volume=1)
        agg.process_tick(late)

        candles = list(agg.candles.values())
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].volume, 1)
        self.assertEqual(candles[0].trade_count, 1)

    def test_flush_all_drains_remaining_candles(self) -> None:
        agg = OHLCVAggregator()
        agg.process_tick(TickModel(ts=1_000_000, price=100.0, symbol="AAPL", volume=1))

        drained = agg.flush_all()
        self.assertEqual(len(drained), 1)
        self.assertEqual(len(agg.candles), 0)


if __name__ == "__main__":
    unittest.main()
