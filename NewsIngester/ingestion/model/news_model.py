from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _dt_to_iso(dt: datetime) -> str:
    # Ensure a stable, timezone-aware representation.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


@dataclass(slots=True)
class NewsRaw:
    id: str
    source: str
    title: str
    content: str
    url: str
    published_at: datetime # convert từ epoch
    image_url: str | None = None
    category: str | None = None
    symbol: str = ""
    ingested_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    raw_payload: dict[str, Any] = field(default_factory=dict)  # giữ nguyên JSON gốc

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["published_at"] = _dt_to_iso(self.published_at)
        d["ingested_at"] = _dt_to_iso(self.ingested_at)
        return d

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
