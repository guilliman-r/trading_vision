"""Typed values for scanner result filters, rows, and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PatternResultFilters:
    symbol: str = ""
    interval: str = ""
    pattern_type: str = ""
    direction: str = ""
    state: str = ""
    minimum_score: float = 0
    lookback_days: int = 90


@dataclass(frozen=True, slots=True)
class PatternResultRow:
    pattern_id: str
    provider_symbol: str
    interval: str
    pattern_type: str
    direction: str
    state: str
    score: float
    started_at: datetime
    confirmed_at: datetime | None
    last_seen_at: datetime
    boundary_price: float
    target_price: float | None
    invalidation_price: float | None
    reasons: tuple[str, ...]
    app_link: str


@dataclass(frozen=True, slots=True)
class ScannerResultsSnapshot:
    rows: tuple[PatternResultRow, ...]
    diagnostics: tuple[tuple[str, str], ...]
