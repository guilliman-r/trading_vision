"""Yahoo Finance adapter; all yfinance-specific behavior stays here."""

from __future__ import annotations

import pandas as pd
import yfinance as yf

from trading_vision.data_quality import DataQualityError, prepare_candles_with_report
from trading_vision.providers.base import FetchResult, MarketDataProvider

PERIOD_BY_INTERVAL = {
    "1d": "2y",
    "1h": "60d",
    "15m": "60d",
    "5m": "1mo",
}


class YahooFinanceProvider(MarketDataProvider):
    name = "Yahoo Finance"

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        if interval not in PERIOD_BY_INTERVAL:
            return FetchResult(symbol=symbol, error=f"Unsupported interval: {interval}")
        try:
            raw = yf.Ticker(symbol).history(
                period=PERIOD_BY_INTERVAL[interval],
                interval=interval,
                auto_adjust=True,
                actions=False,
            )
            if raw.empty:
                return FetchResult(symbol=symbol, error="Yahoo Finance returned no candles")
            normalized = self._normalize_columns(raw)
            prepared = prepare_candles_with_report(normalized, interval, self.name)
            return FetchResult(
                symbol=symbol,
                candles=prepared.candles,
                quality_report=prepared.quality_report,
            )
        except DataQualityError as error:
            return FetchResult(
                symbol=symbol,
                error=f"Yahoo Finance data-quality error: {error}",
                quality_report=error.quality_report,
            )
        except Exception as error:  # yfinance emits several transport exception types
            return FetchResult(symbol=symbol, error=f"Yahoo Finance error: {error}")

    @staticmethod
    def _normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
        normalized = frame.rename(columns=lambda value: str(value).strip().lower())
        normalized.index = pd.to_datetime(normalized.index, utc=True, errors="coerce")
        normalized.index.name = "opened_at_utc"
        return normalized
