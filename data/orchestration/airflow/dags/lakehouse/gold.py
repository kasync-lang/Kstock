"""Gold layer (ClickHouse aggregate_db): idempotent daily load and post-load checks."""
from __future__ import annotations

import json
import os
from datetime import date

from lakehouse.checks import FAIL, PASS, WARN, CheckResult
from lakehouse.layout import GOLD
from lakehouse.ticks import daily_bar_timestamp, market_day_bounds_ms

# Streaming (ohlcv_1m) and batch (ohlcv_1d) volumes may differ by late ticks the stream dropped
RECON_TOLERANCE = float(os.getenv("DQ_RECON_TOLERANCE", "0.02"))

OHLCV_COLUMNS = ["symbol", "timestamp", "open", "high", "low", "close", "volume"]
DQ_COLUMNS = ["run_id", "trade_date", "layer", "dataset", "check_name", "symbol",
              "status", "observed", "threshold", "detail"]

# ohlcv_1d stores one row per trading date (00:00 UTC); matching on the date also catches
# rows written with a different time of day by older loaders
_DAILY_FILTER = "toDate(timestamp) = {day:Date}"
# intraday tables are bucketed in UTC, the trading day spans New York midnight to midnight
_INTRADAY_FILTER = "timestamp >= toDateTime({start:UInt32}) AND timestamp < toDateTime({end:UInt32})"


def _day_params(trade_date: date) -> dict:
    start_ms, end_ms = market_day_bounds_ms(trade_date)
    return {"day": trade_date, "start": start_ms // 1000, "end": end_ms // 1000}


def load_daily_bars(client, trade_date: date, bars: dict[str, dict]) -> int:
    """Replace the day's ohlcv_1d rows for these symbols, so re-runs and backfills never duplicate."""
    if not bars:
        return 0
    params = {**_day_params(trade_date), "symbols": sorted(bars)}
    client.command(f"DELETE FROM ohlcv_1d WHERE {_DAILY_FILTER} AND symbol IN {{symbols:Array(String)}}",
                   parameters=params)
    ts = daily_bar_timestamp(trade_date)
    rows = [[symbol, ts, b["open"], b["high"], b["low"], b["close"], b["volume"]] for symbol, b in sorted(bars.items())]
    client.insert("ohlcv_1d", rows, column_names=OHLCV_COLUMNS)
    return len(rows)


def run_gold_checks(client, trade_date: date, expected_symbols: list[str],
                    recon_tolerance: float = RECON_TOLERANCE) -> list[CheckResult]:
    params = _day_params(trade_date)
    results: list[CheckResult] = []

    def query(sql: str, extra: dict | None = None) -> list[tuple]:
        return client.query(sql, parameters={**params, **(extra or {})}).result_rows

    # 1. one bar per symbol per day
    dupes = query(f"SELECT symbol, count() FROM ohlcv_1d WHERE {_DAILY_FILTER} GROUP BY symbol HAVING count() > 1")
    results.append(CheckResult(GOLD, "ohlcv_1d", "unique_symbol_day", FAIL if dupes else PASS,
                               len(dupes), 0, detail=json.dumps(sorted(s for s, _ in dupes))))

    # 2. OHLC invariants: 0 < low <= open, close <= high and volume >= 0
    bad = query(f"""
        SELECT symbol FROM ohlcv_1d WHERE {_DAILY_FILTER}
          AND NOT (low > 0 AND low <= least(open, close) AND high >= greatest(open, close) AND volume >= 0)""")
    results.append(CheckResult(GOLD, "ohlcv_1d", "ohlc_consistency", FAIL if bad else PASS,
                               len(bad), 0, detail=json.dumps(sorted(s for (s,) in bad))))

    # 3. every symbol promoted from silver reached gold
    present = {s for (s,) in query(f"SELECT DISTINCT symbol FROM ohlcv_1d WHERE {_DAILY_FILTER}")}
    missing = sorted(set(expected_symbols) - present)
    results.append(CheckResult(GOLD, "ohlcv_1d", "completeness", FAIL if missing else PASS,
                               len(missing), 0, detail=json.dumps(missing)))

    # 4. stream vs batch reconciliation: sum(ohlcv_1m.volume) should match ohlcv_1d.volume
    rows = query(f"""
        SELECT d.symbol, d.volume, coalesce(m.volume, 0)
        FROM (SELECT symbol, sum(volume) AS volume FROM ohlcv_1d WHERE {_DAILY_FILTER} GROUP BY symbol) AS d
        LEFT JOIN (SELECT symbol, sum(volume) AS volume FROM ohlcv_1m WHERE {_INTRADAY_FILTER} GROUP BY symbol) AS m
          ON d.symbol = m.symbol""")
    off = {}
    for symbol, batch_vol, stream_vol in rows:
        diff = abs(batch_vol - stream_vol) / batch_vol if batch_vol else 0.0
        if diff > recon_tolerance:
            off[symbol] = round(diff, 4)
    results.append(CheckResult(GOLD, "ohlcv_1m_vs_1d", "volume_reconciliation", WARN if off else PASS,
                               len(off), recon_tolerance, detail=json.dumps(off, sort_keys=True)))
    return results


def record_results(client, run_id: str, trade_date: date, results: list[CheckResult]) -> None:
    if not results:
        return
    rows = [[run_id, trade_date, r.layer, r.dataset, r.check_name, r.symbol,
             r.status, r.observed, r.threshold, r.detail] for r in results]
    client.insert("dq_results", rows, column_names=DQ_COLUMNS)
