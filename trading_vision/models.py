"""Simple data models with no database or user-interface behavior."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Symbol:
    display_symbol: str
    provider_symbol: str
    name: str | None = None
    exchange: str | None = None
    currency: str | None = None
    is_bist: bool = False
    is_active: bool = True
    source: str | None = None
    source_date: str | None = None
    id: int | None = None


@dataclass(frozen=True, slots=True)
class ChartSnapshot:
    symbol: Symbol
    interval: str
    candle_count: int
    latest_candle_at: datetime | None
    fetched_at: datetime | None
    provider_message: str | None = None
