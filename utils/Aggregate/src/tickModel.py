from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


def _first_present(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    raise KeyError(f"missing required field, expected one of: {', '.join(keys)}")


@dataclass(slots=True)
class TickModel:
    ts: int
    price: float
    symbol: str
    volume: int

    def to_dict(self) -> dict[str, int | float | str]:
        return {
            "ts": self.ts,
            "price": self.price,
            "symbol": self.symbol,
            "volume": self.volume,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TickModel":
        if not isinstance(data, Mapping):
            raise TypeError("TickModel.from_dict expects a mapping")

        return cls(
            ts=int(_first_present(data, "ts", "t", "timestamp")),
            price=float(_first_present(data, "price", "p")),
            symbol=str(_first_present(data, "symbol", "s", "sym")),
            volume=int(_first_present(data, "volume", "v", "qty", "size")),
        )

    @classmethod
    def from_json(cls, payload: str | bytes) -> "TickModel":
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        data = json.loads(payload)
        if not isinstance(data, Mapping):
            raise TypeError("TickModel JSON payload must decode to an object")
        return cls.from_dict(data)

    def __str__(self) -> str:
        return self.to_json()


@dataclass(slots=True)
class Candle:
    symbol: str
    bucket_start: int
    open: float
    high: float
    low: float
    close: float
    volume: int
    first_ts: int
    last_ts: int
    trade_count: int = 1

    def to_dict(self) -> dict[str, int | float | str]:
        return {
            "symbol": self.symbol,
            "bucket_start": self.bucket_start,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "first_ts": self.first_ts,
            "last_ts": self.last_ts,
            "trade_count": self.trade_count,
        }
