"""Coordinate symbol resolution, caching, provider fetches, and persistence."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pandas as pd

from trading_vision.models import Symbol
from trading_vision.providers.base import MarketDataProvider
from trading_vision.repositories import find_symbol, get_candles, upsert_candles, upsert_symbol


@dataclass(slots=True)
class ChartLoadResult:
    symbol: Symbol
    candles: pd.DataFrame
    provider_message: str | None = None


class MarketDataService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        provider: MarketDataProvider,
        candle_limit: int,
    ) -> None:
        self.connection = connection
        self.provider = provider
        self.candle_limit = candle_limit

    def load(self, query: str, interval: str, refresh: bool = True) -> ChartLoadResult:
        symbol = self._resolve_symbol(query)
        cached = get_candles(self.connection, symbol.id, interval, self.candle_limit)
        if not refresh and not cached.empty:
            return ChartLoadResult(symbol=symbol, candles=cached)

        fetched = self.provider.fetch_history(symbol.provider_symbol, interval)
        if fetched.succeeded:
            upsert_candles(self.connection, symbol.id, interval, fetched.candles)
            self.connection.commit()
            cached = get_candles(self.connection, symbol.id, interval, self.candle_limit)
            return ChartLoadResult(symbol=symbol, candles=cached)
        if not cached.empty:
            return ChartLoadResult(
                symbol=symbol,
                candles=cached,
                provider_message=f"Showing cached data. {fetched.error}",
            )
        return ChartLoadResult(
            symbol=symbol,
            candles=pd.DataFrame(),
            provider_message=fetched.error,
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
