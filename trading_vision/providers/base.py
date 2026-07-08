"""Small provider contract used by the market-data service."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import pandas as pd

from trading_vision.data_quality import DataQualityReport


@dataclass(slots=True)
class MetadataResult:
    symbol: str
    provider_name: str
    name: str | None = None
    exchange: str | None = None
    currency: str | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


@dataclass(slots=True)
class SymbolValidationResult:
    symbol: str
    error: str | None = None
    metadata: MetadataResult | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


@dataclass(slots=True)
class FetchResult:
    symbol: str
    candles: pd.DataFrame = field(default_factory=pd.DataFrame)
    error: str | None = None
    quality_report: DataQualityReport | None = None
    failure_kind: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None and not self.candles.empty


class MarketDataProvider:
    """Base class that makes alternate data sources easy to add."""

    name = "unknown"

    def validate_symbol(self, symbol: str) -> SymbolValidationResult:
        normalized = normalize_provider_symbol(symbol)
        if not normalized:
            return SymbolValidationResult(symbol=symbol, error="Symbol is required")
        return SymbolValidationResult(symbol=normalized)

    def fetch_metadata(self, symbol: str) -> MetadataResult:
        normalized = normalize_provider_symbol(symbol)
        if not normalized:
            return MetadataResult(
                symbol=symbol,
                provider_name=self.name,
                error="Symbol is required",
            )
        return MetadataResult(symbol=normalized, provider_name=self.name)

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        raise NotImplementedError

    def fetch_history_batch(
        self,
        symbols: Sequence[str],
        interval: str,
        batch_size: int,
    ) -> dict[str, FetchResult]:
        return {symbol: self.fetch_history(symbol, interval) for symbol in symbols}


def normalize_provider_symbol(symbol: str) -> str:
    return symbol.strip().upper()
