"""Download daily OHLCV bars from yfinance and load them into ClickHouse.

Target table:
    aggregate_db.ohlcv_1d (symbol, timestamp, open, high, low, close, volume)

Usage examples:
    # Incremental: for each symbol, fetch from (last stored day + 1) until today
    python -m ingestion.source.yf_ohlcv_loader

    # Explicit range (end is inclusive), replacing any existing rows in that range
    python -m ingestion.source.yf_ohlcv_loader --start 2025-10-01 --end 2026-09-30 --replace

    # Only some symbols, no DB writes
    python -m ingestion.source.yf_ohlcv_loader --symbols AAPL MSFT --dry-run

Connection settings come from env (.env is loaded automatically):
    CLICKHOUSE_HOST (default localhost), CLICKHOUSE_PORT (default 8123),
    CLICKHOUSE_USER (default default), CLICKHOUSE_PASSWORD (default ""),
    CLICKHOUSE_SECURE (default false)
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import date, timedelta
from pathlib import Path

import clickhouse_connect
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SYMBOL_FILE = BASE_DIR / "list_symbol.txt"
TABLE = "aggregate_db.ohlcv_1d"
COLUMNS = ["symbol", "timestamp", "open", "high", "low", "close", "volume"]
DEFAULT_START = date(2000, 1, 1)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def load_symbols(fp: Path) -> list[str]:
    symbols = [s.strip().upper() for s in fp.read_text(encoding="utf-8").splitlines() if s.strip()]
    # de-duplicate while preserving order
    return list(dict.fromkeys(symbols))


def get_client():
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        secure=os.getenv("CLICKHOUSE_SECURE", "false").lower() in ("1", "true", "yes"),
    )


def get_last_dates(client, symbols: list[str]) -> dict[str, date]:
    """Return {symbol: last stored trading date} for symbols already in the table."""
    result = client.query(
        f"SELECT symbol, toDate(max(timestamp)) FROM {TABLE} "
        f"WHERE symbol IN %(symbols)s GROUP BY symbol",
        parameters={"symbols": symbols},
    )
    return {row[0]: row[1] for row in result.result_rows}


def fetch_ohlcv(symbol: str, start: date, end: date, auto_adjust: bool, retries: int = 3) -> pd.DataFrame:
    """Fetch daily bars for [start, end] (end inclusive) and map to the table schema."""
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            raw = yf.Ticker(symbol).history(
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),  # yfinance `end` is exclusive
                interval="1d",
                auto_adjust=auto_adjust,
                actions=False,
            )
            break
        except Exception as e:  # network / rate-limit errors
            last_err = e
            logger.warning("%s: attempt %d/%d failed: %s", symbol, attempt, retries, e)
            time.sleep(2 * attempt)
    else:
        raise RuntimeError(f"{symbol}: failed after {retries} attempts") from last_err

    if raw is None or raw.empty:
        return pd.DataFrame(columns=COLUMNS)

    return to_table_frame(symbol, raw)


def to_table_frame(symbol: str, raw: pd.DataFrame) -> pd.DataFrame:
    """Convert a yfinance history() DataFrame to the ohlcv_1d schema.

    yfinance returns a tz-aware DatetimeIndex at exchange-local midnight
    (e.g. 2025-10-01 00:00:00-04:00). We keep the *trading date* and store it
    as 00:00:00 UTC so the date is unambiguous in ClickHouse.
    """
    idx = pd.DatetimeIndex(raw.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)  # drop tz, keep exchange-local wall clock
    ts = idx.normalize().tz_localize("UTC")

    df = pd.DataFrame(
        {
            "symbol": symbol,
            "timestamp": ts,
            "open": raw["Open"].to_numpy(dtype="float64"),
            "high": raw["High"].to_numpy(dtype="float64"),
            "low": raw["Low"].to_numpy(dtype="float64"),
            "close": raw["Close"].to_numpy(dtype="float64"),
            "volume": raw["Volume"].to_numpy(dtype="float64"),
        }
    )
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df.drop_duplicates(subset=["timestamp"], keep="last").reset_index(drop=True)
    return df


def delete_range(client, symbol: str, start: date, end: date) -> None:
    client.command(
        f"DELETE FROM {TABLE} WHERE symbol = %(symbol)s "
        f"AND toDate(timestamp) BETWEEN %(start)s AND %(end)s",
        parameters={"symbol": symbol, "start": start, "end": end},
    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    p = argparse.ArgumentParser(description="Load daily OHLCV from yfinance into ClickHouse.")
    p.add_argument("--symbols", nargs="+", help="Symbols to load (default: from --symbol-file)")
    p.add_argument("--symbol-file", type=Path, default=DEFAULT_SYMBOL_FILE)
    p.add_argument("--start", type=date.fromisoformat, help="Start date YYYY-MM-DD (default: incremental)")
    p.add_argument("--end", type=date.fromisoformat, default=date.today(), help="End date YYYY-MM-DD, inclusive")
    p.add_argument("--replace", action="store_true",
                   help="Delete existing rows in [start, end] per symbol before insert (requires --start)")
    p.add_argument("--no-adjust", action="store_true", help="Store raw (unadjusted) prices")
    p.add_argument("--sleep", type=float, default=0.3, help="Seconds to sleep between symbols")
    p.add_argument("--dry-run", action="store_true", help="Download only, do not write to ClickHouse")
    args = p.parse_args()

    if args.replace and not args.start:
        p.error("--replace requires --start")

    symbols = [s.upper() for s in args.symbols] if args.symbols else load_symbols(args.symbol_file)
    logger.info("Loading %d symbols", len(symbols))

    client = None if args.dry_run else get_client()
    last_dates: dict[str, date] = {}
    if client is not None and not args.start:
        last_dates = get_last_dates(client, symbols)

    total_rows, failed = 0, []
    for i, symbol in enumerate(symbols, 1):
        if args.start:
            start = args.start
        elif symbol in last_dates:
            start = last_dates[symbol] + timedelta(days=1)
        else:
            start = DEFAULT_START

        if start > args.end:
            logger.info("[%d/%d] %s: up to date", i, len(symbols), symbol)
            continue

        try:
            df = fetch_ohlcv(symbol, start, args.end, auto_adjust=not args.no_adjust)
            if df.empty:
                logger.info("[%d/%d] %s: no data for %s..%s", i, len(symbols), symbol, start, args.end)
                continue

            if client is not None:
                if args.replace:
                    delete_range(client, symbol, start, args.end)
                client.insert_df(TABLE, df[COLUMNS])

            total_rows += len(df)
            logger.info("[%d/%d] %s: %d rows (%s..%s)%s", i, len(symbols), symbol, len(df),
                        df["timestamp"].min().date(), df["timestamp"].max().date(),
                        " [dry-run]" if args.dry_run else "")
        except Exception:
            logger.exception("[%d/%d] %s: failed", i, len(symbols), symbol)
            failed.append(symbol)

        time.sleep(args.sleep)

    logger.info("Done. rows=%d, failed=%d %s", total_rows, len(failed), failed or "")


if __name__ == "__main__":
    main()

