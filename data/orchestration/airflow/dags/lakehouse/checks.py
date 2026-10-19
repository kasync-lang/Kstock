"""Common shape of a data-quality check result (one row in aggregate_db.dq_results)."""
from __future__ import annotations

from dataclasses import asdict, dataclass

PASS = "pass"
WARN = "warn"   # recorded, does not stop the pipeline
FAIL = "fail"   # recorded, stops the downstream layer


@dataclass(frozen=True)
class CheckResult:
    layer: str
    dataset: str
    check_name: str
    status: str
    observed: float
    threshold: float
    symbol: str = ""
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def failed(results: list[CheckResult]) -> list[CheckResult]:
    return [r for r in results if r.status == FAIL]
