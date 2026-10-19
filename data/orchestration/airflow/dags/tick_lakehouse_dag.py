"""Nightly tick lakehouse: raw -> bronze -> silver -> gold, with data-quality gates.

    raw JSONL (tick-recorder)
      -> bronze  : raw lines archived as Parquet in S3, nothing dropped
      -> silver  : parsed, validated, deduplicated, time-ordered ticks; bad rows to quarantine
                   gate: a symbol/day with too many rejected rows is NOT promoted
      -> gold    : ohlcv_1d in ClickHouse, rebuilt idempotently from silver
                   checks: uniqueness, OHLC invariants, completeness, stream-vs-batch reconciliation
    Every check result is stored in aggregate_db.dq_results; any `fail` fails the run.
"""
from __future__ import annotations

import os
from datetime import date

import clickhouse_connect
import pandas as pd
import pendulum
import pyarrow.parquet as pq
from airflow.exceptions import AirflowFailException
from airflow.sdk import dag, get_current_context, task

from api.uploader import S3Uploader
from lakehouse import layout
from lakehouse.checks import failed
from lakehouse.gold import load_daily_bars, record_results, run_gold_checks
from lakehouse.ticks import (
    QUARANTINE_SCHEMA, SILVER_SCHEMA, bronze_to_silver, build_bronze,
    daily_bar, silver_gate, write_parquet,
)

tz_US = pendulum.timezone("America/New_York")


def _trade_date() -> date:
    # Runs after midnight New York time and processes the previous trading day
    logical_date = get_current_context()["logical_date"]
    return logical_date.subtract(days=1).astimezone(tz=tz_US).date()


def _run_id() -> str:
    return get_current_context()["run_id"]


def _clickhouse_call(fn, *args, **kwargs):
    client = clickhouse_connect.get_client(host=os.getenv('CLICKHOUSE_HOST', '192.168.2.100'),
                                         port=int(os.getenv('CLICKHOUSE_PORT', 8123)),
                                         username=os.getenv('CLICKHOUSE_USER', 'dev'),
                                         password=os.getenv('CLICKHOUSE_PASSWORD', 'dev_password'),
                                         database=os.getenv('CLICKHOUSE_DB', 'aggregate_db'))
    try:
        return fn(client, *args, **kwargs)
    finally:
        client.close()


@dag(
    schedule="20 1 * * *",
    dag_id="tick_lakehouse_daily",
    default_args={
        "owner": "kasync",
        "depends_on_past": False,
    },
    start_date=pendulum.datetime(2025, 10, 1, tz=tz_US),
    catchup=False,
    tags=["lakehouse", "data-quality"],
)
def tick_lakehouse_daily():
    @task()
    def symbols_with_raw_data() -> list[str]:
        trade_date = _trade_date()
        with open(layout.SYMBOL_FILE) as f:
            symbols = [s.strip() for s in f if s.strip()]
        return [s for s in symbols if os.path.isdir(layout.raw_dir(s, trade_date))]

    @task(map_index_template="{{ task.op_kwargs['symbol'] }}")
    def bronze(symbol: str) -> dict:
        trade_date = _trade_date()
        path = layout.lake_path(layout.BRONZE, layout.TICKS, symbol, trade_date)
        rows = build_bronze(layout.raw_dir(symbol, trade_date), path)
        S3Uploader().upload_file_to_key(path, layout.s3_key(layout.BRONZE, layout.TICKS, symbol, trade_date))
        return {"symbol": symbol, "bronze_rows": rows}

    @task()
    def silver(bronze_info: dict) -> dict:
        trade_date = _trade_date()
        symbol = bronze_info["symbol"]
        bronze_df = pq.read_table(layout.lake_path(layout.BRONZE, layout.TICKS, symbol, trade_date)).to_pandas()
        silver_df, quarantine_df, report = bronze_to_silver(bronze_df, symbol, trade_date)

        uploader = S3Uploader()
        for layer, df, schema in ((layout.SILVER, silver_df, SILVER_SCHEMA),
                                  (layout.QUARANTINE, quarantine_df, QUARANTINE_SCHEMA)):
            if layer == layout.QUARANTINE and df.empty:
                continue
            path = layout.lake_path(layer, layout.TICKS, symbol, trade_date)
            write_parquet(df, schema, path)
            uploader.upload_file_to_key(path, layout.s3_key(layer, layout.TICKS, symbol, trade_date))

        results = silver_gate(report)
        _clickhouse_call(record_results, _run_id(), trade_date, results)
        # A failed gate only holds back this symbol; the others still reach gold
        return {**report.to_dict(), "promoted": not failed(results)}

    @task()
    def gold(reports: list[dict]) -> list[str]:
        trade_date = _trade_date()
        bars = {}
        for r in reports:
            if r["promoted"]:
                path = layout.lake_path(layout.SILVER, layout.TICKS, r["symbol"], trade_date)
                bars[r["symbol"]] = daily_bar(pd.read_parquet(path))
        _clickhouse_call(load_daily_bars, trade_date, bars)
        return sorted(bars)

    @task()
    def gold_quality(loaded: list[str], reports: list[dict]) -> None:
        trade_date = _trade_date()
        results = _clickhouse_call(run_gold_checks, trade_date, expected_symbols=loaded)
        _clickhouse_call(record_results, _run_id(), trade_date, results)

        held_back = [r["symbol"] for r in reports if not r["promoted"]]
        problems = [f"{r.layer}.{r.dataset}.{r.check_name}" for r in failed(results)]
        if held_back:
            problems.append(f"silver gate held back {held_back}")
        if problems:
            # Fails the run so it alerts; details are in aggregate_db.dq_results
            raise AirflowFailException("data quality failed: " + "; ".join(problems))

    symbols = symbols_with_raw_data()
    reports = silver.expand(bronze_info=bronze.expand(symbol=symbols))
    gold_quality(gold(reports), reports)


tick_lakehouse_daily()
