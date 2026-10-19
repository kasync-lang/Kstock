"""Where each layer lives, locally and in the S3 data lake.

    raw/<symbol>/<date>/part-*.jsonl                 landing zone written by tick-recorder
    lake/bronze/ticks/symbol=<s>/date=<d>.parquet    raw lines, untouched + lineage columns
    lake/silver/ticks/symbol=<s>/date=<d>.parquet    parsed, validated, deduplicated, sorted
    lake/quarantine/ticks/symbol=<s>/date=<d>.parquet  rejected rows + dq_reason
    gold                                            ClickHouse aggregate_db.ohlcv_* tables

The S3 key mirrors the local path below lake/, so the bucket is browsable by layer.
"""
from __future__ import annotations

import os
from datetime import date

DATA_ROOT = os.getenv("DATA_ROOT", "/opt/airflow/data")
RAW_ROOT = os.path.join(DATA_ROOT, "raw")
LAKE_ROOT = os.path.join(DATA_ROOT, "lake")
SYMBOL_FILE = os.path.join(DATA_ROOT, "list_symbol.txt")

BRONZE = "bronze"
SILVER = "silver"
QUARANTINE = "quarantine"
GOLD = "gold"

TICKS = "ticks"


def raw_dir(symbol: str, trade_date: date) -> str:
    return os.path.join(RAW_ROOT, symbol, trade_date.isoformat())


def s3_key(layer: str, dataset: str, symbol: str, trade_date: date) -> str:
    return f"{layer}/{dataset}/symbol={symbol}/date={trade_date.isoformat()}.parquet"


def lake_path(layer: str, dataset: str, symbol: str, trade_date: date) -> str:
    return os.path.join(LAKE_ROOT, s3_key(layer, dataset, symbol, trade_date))
