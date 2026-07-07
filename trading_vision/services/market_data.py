"""Coordinate symbol resolution, caching, provider fetches, and persistence."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd

from trading_vision.candle_completion import mark_bist_candle_completion
from trading_vision.data_quality import DataQualityReport
from trading_vision.market_calendar import BistSessionCalendar
from trading_vision.models import PatternMatch, Symbol
from trading_vision.providers.base import MarketDataProvider
from trading_vision.repositories import find_symbol, get_candles, upsert_candles, upsert_symbol


@dataclass(slots=True)
class ChartLoadResult:
    symbol: Symbol
    candles: pd.DataFrame
    from_cache: bool = False
    provider_message: str | None = None
    patterns: tuple[PatternMatch, ...] = ()
    quality_report: DataQualityReport | None = None


class MarketDataService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        provider: MarketDataProvider,
        candle_limit: int,
        provider_delay_seconds: int = 60,
        calendar: BistSessionCalendar | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.connection = connection
        self.provider = provider
        self.candle_limit = candle_limit
        self.provider_delay_seconds = provider_delay_seconds
        self.calendar = calendar or BistSessionCalendar()
        self.now = now or (lambda: datetime.now(UTC))

    def load(self, query: str, interval: str, refresh: bool = True) -> ChartLoadResult:
        symbol = self._resolve_symbol(query)
        cached = get_candles(self.connection, symbol.id, interval, self.candle_limit)
        cached = self._completion_flags(symbol, cached, interval)
        if not refresh and not cached.empty:
            return ChartLoadResult(symbol=symbol, candles=cached, from_cache=True)

        fetched = self.provider.fetch_history(symbol.provider_symbol, interval)
        if fetched.succeeded:
            prepared = self._completion_flags(symbol, fetched.candles, interval)
            upsert_candles(self.connection, symbol.id, interval, prepared)
            self.connection.commit()
            cached = get_candles(self.connection, symbol.id, interval, self.candle_limit)
            return ChartLoadResult(
                symbol=symbol,
                candles=cached,
                quality_report=fetched.quality_report,
            )
        if not cached.empty:
            return ChartLoadResult(
                symbol=symbol,
                candles=cached,
                from_cache=True,
                provider_message=f"Showing cached data. {fetched.error}",
                quality_report=fetched.quality_report,
            )
        return ChartLoadResult(
            symbol=symbol,
            candles=pd.DataFrame(),
            provider_message=fetched.error,
            quality_report=fetched.quality_report,
        )

    def _completion_flags(
        self,
        symbol: Symbol,
        candles: pd.DataFrame,
        interval: str,
    ) -> pd.DataFrame:
        if not symbol.is_bist or candles.empty:
            return candles
        return mark_bist_candle_completion(
            candles,
            interval,
            self.now(),
            self.provider_delay_seconds,
            self.calendar,
        )

    def _resolve_symbol(self, query: str) -> Symbol:
        normalized = query.strip().upper()
        if not normalized:
            raise ValueError("Enter a symbol")
        known = find_symbol(self.connection, normalized)
        if known:
            return known
        generic = Symbol(display_symbol=normalized, provider_symbol=normalized, source="user")
        stored = upsert_symbol(self.connection, generic)
        self.connection.commit()
        return stored
