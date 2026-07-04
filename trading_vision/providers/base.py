"""Small provider contract used by the market-data service."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass(slots=True)
class FetchResult:
    symbol: str
    candles: pd.DataFrame = field(default_factory=pd.DataFrame)
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None and not self.candles.empty


class MarketDataProvider:
    """Base class that makes alternate data sources easy to add."""

    name = "unknown"

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        raise NotImplementedError
