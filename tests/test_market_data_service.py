from __future__ import annotations

import pandas as pd

from trading_vision.data_quality import prepare_candles
from trading_vision.database import connect
from trading_vision.models import Symbol
from trading_vision.providers.base import FetchResult, MarketDataProvider
from trading_vision.repositories import seed_symbols
from trading_vision.services.market_data import MarketDataService


class StaticProvider(MarketDataProvider):
    name = "fixture"

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        frame = pd.DataFrame(
            {
                "open": [10.0, 11.0],
                "high": [12.0, 13.0],
                "low": [9.0, 10.0],
                "close": [11.0, 12.0],
                "volume": [100.0, 150.0],
            },
            index=pd.to_datetime(["2025-01-01", "2025-01-02"], utc=True),
        )
        candles = prepare_candles(frame, interval, self.name)
        return FetchResult(symbol=symbol, candles=candles)


def test_bist_display_symbol_resolves_to_yahoo_symbol(database_path) -> None:
    with connect(database_path) as connection:
        seed_symbols(connection, [Symbol("THYAO", "THYAO.IS", is_bist=True)])
        service = MarketDataService(connection, StaticProvider(), candle_limit=100)
        result = service.load("thyao", "1d")
    assert result.symbol.provider_symbol == "THYAO.IS"
    assert len(result.candles) == 2


def test_unknown_symbol_is_kept_unchanged(database_path) -> None:
    with connect(database_path) as connection:
        service = MarketDataService(connection, StaticProvider(), candle_limit=100)
        result = service.load("aapl", "1d")
    assert result.symbol.provider_symbol == "AAPL"
