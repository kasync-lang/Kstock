import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow.parquet as pq
import pytest

from lakehouse.checks import FAIL, PASS, WARN
from lakehouse.ticks import (
    BRONZE_SCHEMA, QUARANTINE_SCHEMA, SILVER_SCHEMA, bronze_to_silver, build_bronze,
    daily_bar, silver_gate, write_parquet,
)

DAY = date(2026, 6, 4)
NY = ZoneInfo("America/New_York")


def ts(hour: int, minute: int = 0) -> int:
    return int(datetime(2026, 6, 4, hour, minute, tzinfo=NY).timestamp() * 1000)


def line(**fields) -> str:
    msg = {"t": ts(10), "p": 420.0, "v": 10, "c": ["1"], "s": "TSLA"}
    msg.update(fields)
    return json.dumps({k: v for k, v in msg.items() if v is not ...})


def bronze_df(lines: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"raw": lines, "source_file": "part-00001.jsonl", "line_no": range(1, len(lines) + 1)})


def test_valid_ticks_are_sorted_and_typed():
    silver, quarantine, report = bronze_to_silver(
        bronze_df([line(t=ts(11), p=421.5), line(t=ts(10), p=420.0)]), "TSLA", DAY)

    assert quarantine.empty
    assert list(silver["price"]) == [420.0, 421.5]
    assert str(silver["event_time"].dt.tz) == "UTC"
    assert report.silver_rows == 2 and report.rejected_rows == 0


def test_exact_duplicates_are_dropped_not_quarantined():
    # Same trade re-sent by the feed (seen in real TSLA data)
    silver, quarantine, report = bronze_to_silver(
        bronze_df([line(), line(), line(v=40)]), "TSLA", DAY)

    assert report.duplicate_rows == 1
    assert len(silver) == 2
    assert quarantine.empty


@pytest.mark.parametrize("raw, reason", [
    ("{not json", "invalid_json"),
    ('["a list"]', "invalid_json"),
    (line(p=...), "missing_field"),
    (line(v="ten"), "invalid_type"),
    (line(p=0), "non_positive_price"),
    (line(p=-1.5), "non_positive_price"),
    (line(v=-3), "negative_volume"),
    (line(s="AAPL"), "symbol_mismatch"),
    (line(t=ts(10) + 24 * 3600 * 1000), "outside_trade_date"),
])
def test_invalid_rows_go_to_quarantine_with_reason(raw, reason):
    silver, quarantine, report = bronze_to_silver(bronze_df([line(), raw]), "TSLA", DAY)

    assert len(silver) == 1
    assert list(quarantine["dq_reason"]) == [reason]
    assert quarantine["line_no"].tolist() == [2]          # lineage back to the raw file
    assert report.rejected_by_reason == {reason: 1}


def test_trade_date_follows_new_york_calendar():
    # 23:30 New York is already the next day in UTC but still belongs to DAY
    silver, quarantine, _ = bronze_to_silver(bronze_df([line(t=ts(23, 30))]), "TSLA", DAY)
    assert len(silver) == 1 and quarantine.empty


def test_silver_gate_blocks_high_reject_ratio():
    _, _, report = bronze_to_silver(bronze_df([line(), "{bad", "{bad", line(t=ts(12))]), "TSLA", DAY)

    results = {r.check_name: r for r in silver_gate(report, max_reject_ratio=0.05)}
    assert results["non_empty"].status == PASS
    assert results["reject_ratio"].status == FAIL
    assert results["reject_ratio"].observed == 0.5
    assert json.loads(results["reject_ratio"].detail) == {"invalid_json": 2}


def test_many_duplicates_only_warn():
    _, _, report = bronze_to_silver(bronze_df([line(), line(), line(), line(t=ts(12))]), "TSLA", DAY)

    results = {r.check_name: r for r in silver_gate(report, max_duplicate_ratio=0.05)}
    assert results["duplicate_ratio"].status == WARN
    assert results["duplicate_ratio"].detail == "2/4 rows"
    assert results["reject_ratio"].status == PASS


def test_silver_gate_blocks_empty_day():
    _, _, report = bronze_to_silver(bronze_df(["{bad"]), "TSLA", DAY)
    assert {r.check_name: r.status for r in silver_gate(report)}["non_empty"] == FAIL


def test_daily_bar_uses_event_time_not_file_order():
    silver, _, _ = bronze_to_silver(bronze_df([
        line(t=ts(15), p=12.0, v=5),   # last trade, written first
        line(t=ts(10), p=10.0, v=1),   # first trade
        line(t=ts(12), p=15.0, v=2),
        line(t=ts(13), p=9.0, v=3),
    ]), "TSLA", DAY)

    assert daily_bar(silver) == {"open": 10.0, "high": 15.0, "low": 9.0, "close": 12.0, "volume": 11.0}


def test_build_bronze_keeps_every_line_with_lineage(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "part-00001.jsonl").write_text(line() + "\n\n{broken\n")
    (raw_dir / "part-00002.jsonl").write_text(line(t=ts(11)) + "\n")
    out = tmp_path / "bronze" / "date=2026-06-04.parquet"

    assert build_bronze(str(raw_dir), str(out), batch_size=1) == 3
    table = pq.read_table(out)
    assert table.schema == BRONZE_SCHEMA
    assert table.column("source_file").to_pylist() == ["part-00001.jsonl", "part-00001.jsonl", "part-00002.jsonl"]
    assert table.column("line_no").to_pylist() == [1, 3, 1]
    assert table.column("raw").to_pylist()[1] == "{broken"


def test_silver_and_quarantine_parquet_schemas(tmp_path):
    silver, quarantine, _ = bronze_to_silver(bronze_df([line(), "{bad"]), "TSLA", DAY)
    write_parquet(silver, SILVER_SCHEMA, str(tmp_path / "s.parquet"))
    write_parquet(quarantine, QUARANTINE_SCHEMA, str(tmp_path / "q.parquet"))

    assert pq.read_table(tmp_path / "s.parquet").schema == SILVER_SCHEMA
    assert pq.read_table(tmp_path / "q.parquet").column("dq_reason").to_pylist() == ["invalid_json"]
