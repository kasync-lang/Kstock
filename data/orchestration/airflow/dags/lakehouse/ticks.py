"""Tick dataset: raw JSONL -> bronze -> silver (+ quarantine) -> daily OHLCV bar."""
from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from glob import glob
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from lakehouse.checks import FAIL, PASS, WARN, CheckResult
from lakehouse.layout import SILVER, TICKS

MARKET_TZ = ZoneInfo("America/New_York")

# Raw message fields produced by market-collector: t=epoch ms, p=price, v=size, s=symbol, c=conditions
REQUIRED_FIELDS = ("t", "p", "v", "s")

# Silver gate: a symbol/day is not promoted to gold when too much of it is bad data
MAX_REJECT_RATIO = float(os.getenv("DQ_MAX_REJECT_RATIO", "0.05"))
# Feed health signal only: duplicates are removed either way
MAX_DUPLICATE_RATIO = float(os.getenv("DQ_MAX_DUPLICATE_RATIO", "0.05"))

BRONZE_SCHEMA = pa.schema([
    ("raw", pa.string()),
    ("source_file", pa.string()),
    ("line_no", pa.int64()),
])

SILVER_SCHEMA = pa.schema([
    ("symbol", pa.string()),
    ("event_time", pa.timestamp("ms", tz="UTC")),
    ("ts_ms", pa.int64()),
    ("price", pa.float64()),
    ("volume", pa.int64()),
    ("conditions", pa.list_(pa.string())),
])

QUARANTINE_SCHEMA = BRONZE_SCHEMA.append(pa.field("dq_reason", pa.string()))


# --------------------------------------------------------------------------- bronze

def build_bronze(raw_dir: str, output_file: str, batch_size: int = 50_000) -> int:
    """Copy every raw line as-is into Parquet, adding lineage columns. Returns row count.

    Bronze never parses or drops anything, so a bad line can always be traced back
    to the exact file and line it came from.
    """
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    rows = 0
    with pq.ParquetWriter(output_file, BRONZE_SCHEMA) as writer:
        batch: dict[str, list] = {"raw": [], "source_file": [], "line_no": []}
        for part in sorted(glob(os.path.join(raw_dir, "part-*.jsonl"))):
            with open(part, encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    line = line.rstrip("\n")
                    if not line:
                        continue
                    batch["raw"].append(line)
                    batch["source_file"].append(os.path.basename(part))
                    batch["line_no"].append(line_no)
                    rows += 1
                    if len(batch["raw"]) >= batch_size:
                        writer.write_table(pa.table(batch, schema=BRONZE_SCHEMA))
                        batch = {k: [] for k in batch}
        if batch["raw"]:
            writer.write_table(pa.table(batch, schema=BRONZE_SCHEMA))
    return rows


# --------------------------------------------------------------------------- silver

@dataclass
class TickQualityReport:
    symbol: str
    trade_date: str
    bronze_rows: int = 0
    silver_rows: int = 0
    duplicate_rows: int = 0
    rejected_rows: int = 0
    rejected_by_reason: dict[str, int] = field(default_factory=dict)

    @property
    def reject_ratio(self) -> float:
        return self.rejected_rows / self.bronze_rows if self.bronze_rows else 0.0

    @property
    def duplicate_ratio(self) -> float:
        return self.duplicate_rows / self.bronze_rows if self.bronze_rows else 0.0

    def to_dict(self) -> dict:
        return {**asdict(self), "reject_ratio": self.reject_ratio, "duplicate_ratio": self.duplicate_ratio}


def market_day_bounds_ms(trade_date: date) -> tuple[int, int]:
    start = datetime.combine(trade_date, time.min, tzinfo=MARKET_TZ)
    end = start + timedelta(days=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _validate(raw: str, symbol: str, day_start_ms: int, day_end_ms: int) -> tuple[dict | None, str | None]:
    """Parse one raw line. Returns (tick, None) when valid, otherwise (None, reason)."""
    try:
        msg = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None, "invalid_json"
    if not isinstance(msg, dict):
        return None, "invalid_json"
    if any(msg.get(k) is None for k in REQUIRED_FIELDS):
        return None, "missing_field"
    try:
        ts_ms = int(msg["t"])
        price = float(msg["p"])
        volume = int(msg["v"])
    except (TypeError, ValueError):
        return None, "invalid_type"
    if not math.isfinite(price) or price <= 0:
        return None, "non_positive_price"
    if volume < 0:
        return None, "negative_volume"
    if str(msg["s"]).strip() != symbol:
        return None, "symbol_mismatch"
    if not day_start_ms <= ts_ms < day_end_ms:
        return None, "outside_trade_date"
    conditions = msg.get("c") or []
    if not isinstance(conditions, list):
        conditions = [conditions]
    return {
        "symbol": symbol,
        "ts_ms": ts_ms,
        "price": price,
        "volume": volume,
        "conditions": [str(c) for c in conditions],
    }, None


def bronze_to_silver(
    bronze: pd.DataFrame, symbol: str, trade_date: date
) -> tuple[pd.DataFrame, pd.DataFrame, TickQualityReport]:
    """Validate every bronze row. Returns (silver, quarantine, report).

    silver     : valid ticks, exact duplicates removed, sorted by event time
    quarantine : bronze rows that failed a rule, with the rule name in dq_reason
    """
    day_start_ms, day_end_ms = market_day_bounds_ms(trade_date)
    report = TickQualityReport(symbol=symbol, trade_date=trade_date.isoformat(), bronze_rows=len(bronze))

    valid: list[dict] = []
    rejected_idx: list[int] = []
    reasons: list[str] = []
    for idx, raw in zip(bronze.index, bronze["raw"]):
        tick, reason = _validate(raw, symbol, day_start_ms, day_end_ms)
        if reason is None:
            valid.append(tick)
        else:
            rejected_idx.append(idx)
            reasons.append(reason)

    quarantine = bronze.loc[rejected_idx].copy()
    quarantine["dq_reason"] = reasons
    report.rejected_rows = len(quarantine)
    report.rejected_by_reason = quarantine["dq_reason"].value_counts().to_dict() if reasons else {}

    silver = pd.DataFrame(valid, columns=["symbol", "ts_ms", "price", "volume", "conditions"])
    # The feed re-sends identical trades on reconnect; an exact repeat is a duplicate, not a new trade
    dedup_key = silver[["ts_ms", "price", "volume"]].assign(c=silver["conditions"].map(tuple))
    duplicated = dedup_key.duplicated()
    report.duplicate_rows = int(duplicated.sum())
    silver = silver[~duplicated].sort_values("ts_ms", kind="stable").reset_index(drop=True)
    silver.insert(1, "event_time", pd.to_datetime(silver["ts_ms"], unit="ms", utc=True))
    report.silver_rows = len(silver)
    return silver, quarantine, report


def silver_gate(report: TickQualityReport, max_reject_ratio: float = MAX_REJECT_RATIO,
                max_duplicate_ratio: float = MAX_DUPLICATE_RATIO) -> list[CheckResult]:
    """Dataset-level checks that decide whether this symbol/day may be promoted to gold."""
    def result(name: str, ok: bool, observed: float, threshold: float, detail: str = "",
               bad: str = FAIL) -> CheckResult:
        return CheckResult(SILVER, TICKS, name, PASS if ok else bad, float(observed), float(threshold),
                           symbol=report.symbol, detail=detail)

    return [
        result("non_empty", report.silver_rows > 0, report.silver_rows, 1),
        result("reject_ratio", report.reject_ratio <= max_reject_ratio, report.reject_ratio, max_reject_ratio,
               detail=json.dumps(report.rejected_by_reason, sort_keys=True)),
        result("duplicate_ratio", report.duplicate_ratio <= max_duplicate_ratio, report.duplicate_ratio,
               max_duplicate_ratio, detail=f"{report.duplicate_rows}/{report.bronze_rows} rows", bad=WARN),
    ]


def write_parquet(df: pd.DataFrame, schema: pa.Schema, output_file: str) -> None:
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    table = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
    pq.write_table(table, output_file)


# --------------------------------------------------------------------------- gold

def daily_bar(silver: pd.DataFrame) -> dict:
    """Daily OHLCV from time-ordered silver ticks."""
    if silver.empty:
        raise ValueError("cannot build a daily bar from an empty silver dataset")
    ordered = silver.sort_values("ts_ms", kind="stable")
    return {
        "open": float(ordered["price"].iloc[0]),
        "high": float(ordered["price"].max()),
        "low": float(ordered["price"].min()),
        "close": float(ordered["price"].iloc[-1]),
        "volume": float(ordered["volume"].sum()),
    }


def daily_bar_timestamp(trade_date: date) -> datetime:
    """Timestamp stored in ohlcv_1d for a trading day: the date at 00:00 UTC (existing convention)."""
    return datetime.combine(trade_date, time.min, tzinfo=timezone.utc)
