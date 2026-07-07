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

REQUIRED_PRICE_COLUMNS = {"open", "high", "low", "close", "volume"}


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
            normalized = normalize_yahoo_history_frame(raw, symbol)
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


def normalize_yahoo_history_frame(frame: pd.DataFrame, symbol: str | None = None) -> pd.DataFrame:
    """Return Yahoo history data in the app's internal OHLCV column shape."""

    normalized = _select_symbol_frame(frame, symbol)
    normalized = normalized.rename(columns=lambda value: str(value).strip().lower())
    normalized.index = pd.to_datetime(normalized.index, utc=True, errors="coerce")
    normalized.index.name = "opened_at_utc"
    return normalized


def _select_symbol_frame(frame: pd.DataFrame, symbol: str | None) -> pd.DataFrame:
    if not isinstance(frame.columns, pd.MultiIndex):
        return frame.copy()

    expected_symbol = _normalize_symbol(symbol) if symbol else ""
    candidates: list[tuple[str, pd.DataFrame]] = []
    for level_index in range(frame.columns.nlevels):
        for level_value in frame.columns.get_level_values(level_index).unique():
            selected = frame.xs(level_value, axis=1, level=level_index, drop_level=True)
            selected = _flatten_to_price_columns(selected)
            if _has_required_prices(selected):
                candidate_symbol = _normalize_symbol(level_value)
                if expected_symbol and candidate_symbol == expected_symbol:
                    return selected
                candidates.append((candidate_symbol, selected))

    if expected_symbol:
        raise ValueError(f"Yahoo data did not contain symbol: {symbol}")
    if len(candidates) == 1:
        return candidates[0][1]
    raise ValueError("Yahoo multi-symbol data requires a symbol to choose one ticker")


def _flatten_to_price_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame.columns, pd.MultiIndex):
        return frame.copy()
    for level_index in range(frame.columns.nlevels):
        labels = {_normalize_column(value) for value in frame.columns.get_level_values(level_index)}
        if REQUIRED_PRICE_COLUMNS.issubset(labels):
            flattened = frame.copy()
            flattened.columns = flattened.columns.get_level_values(level_index)
            return flattened
    return frame.copy()


def _has_required_prices(frame: pd.DataFrame) -> bool:
    return REQUIRED_PRICE_COLUMNS.issubset({_normalize_column(column) for column in frame.columns})


def _normalize_column(value: object) -> str:
    return str(value).strip().lower()


def _normalize_symbol(value: object) -> str:
    return str(value).strip().upper()
