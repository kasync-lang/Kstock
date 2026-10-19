"""Gold load + checks against a real ClickHouse.

Runs only when CLICKHOUSE_TEST_HOST is set, e.g. against the local stack:
    CLICKHOUSE_TEST_HOST=localhost pytest tests/test_lakehouse_gold.py
"""
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from lakehouse.checks import FAIL, PASS, WARN
from lakehouse.gold import load_daily_bars, record_results, run_gold_checks
from lakehouse.ticks import daily_bar_timestamp

HOST = os.getenv("CLICKHOUSE_TEST_HOST")
pytestmark = pytest.mark.skipif(not HOST, reason="CLICKHOUSE_TEST_HOST not set")

DDL_DIR = Path(__file__).parents[3] / "processing" / "ohlcv-aggregator" / "aggregate_db"
DAY = date(2026, 6, 4)


@pytest.fixture()
def client():
    clickhouse_connect = pytest.importorskip("clickhouse_connect")
    admin = clickhouse_connect.get_client(
        host=HOST, port=int(os.getenv("CLICKHOUSE_TEST_PORT", 8123)),
        username=os.getenv("CLICKHOUSE_TEST_USER", "dev"), password=os.getenv("CLICKHOUSE_TEST_PASSWORD", "dev_password"))
    db = f"dq_test_{uuid.uuid4().hex[:8]}"
    admin.command(f"CREATE DATABASE {db}")
    c = clickhouse_connect.get_client(
        host=HOST, port=int(os.getenv("CLICKHOUSE_TEST_PORT", 8123)), database=db,
        username=os.getenv("CLICKHOUSE_TEST_USER", "dev"), password=os.getenv("CLICKHOUSE_TEST_PASSWORD", "dev_password"))
    for name in ("ohlcv_1d", "ohlcv_1m", "dq_results"):
        c.command((DDL_DIR / f"{name}.sql").read_text())
    yield c
    admin.command(f"DROP DATABASE {db}")


def bar(o, h, l, c, v):
    return {"open": o, "high": h, "low": l, "close": c, "volume": v}


def minute(c, symbol, hour, volume):
    ts = datetime(2026, 6, 4, hour, tzinfo=timezone.utc)
    c.insert("ohlcv_1m", [[symbol, ts, 1.0, 1.0, 1.0, 1.0, volume]],
             column_names=["symbol", "timestamp", "open", "high", "low", "close", "volume"])


def statuses(results):
    return {r.check_name: r.status for r in results}


def test_load_is_idempotent(client):
    bars = {"AAPL": bar(10, 12, 9, 11, 100), "TSLA": bar(20, 21, 19, 20, 50)}
    load_daily_bars(client, DAY, bars)
    load_daily_bars(client, DAY, bars)          # re-run / backfill

    rows = client.query("SELECT symbol, timestamp, close FROM ohlcv_1d ORDER BY symbol").result_rows
    assert [(s, c) for s, _, c in rows] == [("AAPL", 11.0), ("TSLA", 20.0)]
    assert rows[0][1].replace(tzinfo=timezone.utc).timestamp() == daily_bar_timestamp(DAY).timestamp()


def test_reload_cleans_rows_from_older_loaders(client):
    # the previous DAG stored daily bars at 05:20 next to the 00:00 history row
    legacy = datetime(2026, 6, 4, 5, 20, tzinfo=timezone.utc)
    client.insert("ohlcv_1d", [["AAPL", daily_bar_timestamp(DAY), 10, 12, 9, 11, 100],
                               ["AAPL", legacy, 10, 12, 9, 11, 100]],
                  column_names=["symbol", "timestamp", "open", "high", "low", "close", "volume"])
    assert statuses(run_gold_checks(client, DAY, ["AAPL"]))["unique_symbol_day"] == FAIL

    load_daily_bars(client, DAY, {"AAPL": bar(10, 12, 9, 11, 100)})
    assert client.query("SELECT count() FROM ohlcv_1d").result_rows[0][0] == 1
    assert statuses(run_gold_checks(client, DAY, ["AAPL"]))["unique_symbol_day"] == PASS


def test_checks_pass_on_clean_day(client):
    load_daily_bars(client, DAY, {"AAPL": bar(10, 12, 9, 11, 100)})
    minute(client, "AAPL", 14, 60)
    minute(client, "AAPL", 15, 40)

    assert set(statuses(run_gold_checks(client, DAY, ["AAPL"])).values()) == {PASS}


def test_checks_catch_broken_gold(client):
    load_daily_bars(client, DAY, {"AAPL": bar(10, 12, 9, 11, 100), "BAD": bar(10, 8, 9, 11, 5)})
    # a duplicate written outside the idempotent loader
    client.insert("ohlcv_1d", [["AAPL", daily_bar_timestamp(DAY), 10, 12, 9, 11, 100]],
                  column_names=["symbol", "timestamp", "open", "high", "low", "close", "volume"])
    minute(client, "AAPL", 14, 50)              # stream saw only half the volume

    results = run_gold_checks(client, DAY, ["AAPL", "BAD", "MSFT"])
    assert statuses(results) == {
        "unique_symbol_day": FAIL,
        "ohlc_consistency": FAIL,
        "completeness": FAIL,                   # MSFT promoted but missing
        "volume_reconciliation": WARN,
    }

    record_results(client, "run-1", DAY, results)
    stored = client.query("SELECT check_name, status FROM dq_results ORDER BY check_name").result_rows
    assert dict(stored)["completeness"] == "fail"
