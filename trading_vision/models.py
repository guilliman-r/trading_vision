"""Simple data models with no database or user-interface behavior."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


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
class Candle:
    """One validated OHLCV bar independent of storage and chart rendering."""

    interval: str
    opened_at_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    is_complete: bool
    is_adjusted: bool
    source: str
    fetched_at_utc: datetime
    symbol_id: int | None = None

    def __post_init__(self) -> None:
        _require_aware_time(self.opened_at_utc, "opened_at_utc")
        _require_aware_time(self.fetched_at_utc, "fetched_at_utc")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("Candle prices must be positive")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("Candle high must be greater than or equal to open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("Candle low must be less than or equal to open, close, and high")
        if self.volume is not None and self.volume < 0:
            raise ValueError("Candle volume must be null or non-negative")


@dataclass(frozen=True, slots=True)
class ChartSnapshot:
    symbol: Symbol
    interval: str
    candle_count: int
    latest_candle_at: datetime | None
    fetched_at: datetime | None
    provider_message: str | None = None


@dataclass(frozen=True, slots=True)
class Pivot:
    """A local high or low that became knowable after its confirmation window."""

    index: int
    confirmation_index: int
    kind: str
    occurred_at: datetime
    confirmed_at: datetime
    price: float
    atr: float
    prominence_percent: float
    prominence_atr: float


@dataclass(frozen=True, slots=True)
class PatternPoint:
    label: str
    index: int
    occurred_at: datetime
    price: float


@dataclass(frozen=True, slots=True)
class PatternMatch:
    """Detector output independent of storage and user-interface concerns."""

    pattern_type: str
    direction: str
    state: str
    started_at: datetime
    ended_at: datetime | None
    confirmed_at: datetime | None
    score: float
    boundary_price: float
    target_price: float | None
    invalidation_price: float | None
    points: tuple[PatternPoint, ...]
    reasons: tuple[str, ...]
    parameters: dict[str, Any]
    detector_version: str


@dataclass(frozen=True, slots=True)
class PatternTransition:
    id: int
    pattern_id: str
    old_state: str | None
    new_state: str
    changed_at: datetime
    reason: str


@dataclass(frozen=True, slots=True)
class AlertRule:
    id: int
    name: str
    minimum_score: float
    required_state: str
    pattern_types: tuple[str, ...]
    is_active: bool


@dataclass(frozen=True, slots=True)
class Watchlist:
    id: int
    name: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class WatchlistItem:
    watchlist_id: int
    symbol: Symbol
    position: int
    scan_intervals: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AlertEvent:
    id: int
    fingerprint: str
    pattern_id: str
    provider_symbol: str
    interval: str
    pattern_type: str
    direction: str
    state: str
    score: float
    event_at: datetime
    boundary_price: float
    target_price: float | None
    app_link: str
    created_at: datetime
    acknowledged_at: datetime | None


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
