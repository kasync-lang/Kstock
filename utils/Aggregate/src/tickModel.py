from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
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
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "TickModel":
        return cls(
            ts=int(data["t"]),
            price=float(data["p"]),
            symbol=str(data["s"]),
            volume=int(data["v"]),
        )
    def __str__(self):
        return str(self.to_dict())


@dataclass
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
