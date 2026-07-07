"""Yahoo Finance adapter; all yfinance-specific behavior stays here."""

from __future__ import annotations

import logging
from time import perf_counter

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
LOGGER = logging.getLogger(__name__)


class YahooFinanceProvider(MarketDataProvider):
    name = "Yahoo Finance"

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        if interval not in PERIOD_BY_INTERVAL:
            return FetchResult(symbol=symbol, error=f"Unsupported interval: {interval}")
        started = perf_counter()
        try:
            raw = yf.Ticker(symbol).history(
                period=PERIOD_BY_INTERVAL[interval],
                interval=interval,
                auto_adjust=True,
                actions=False,
            )
            if raw.empty:
                _log_history_failure(symbol, interval, started, "no candles")
                return FetchResult(symbol=symbol, error="Yahoo Finance returned no candles")
            normalized = normalize_yahoo_history_frame(raw, symbol)
            prepared = prepare_candles_with_report(normalized, interval, self.name)
            _log_history_success(symbol, interval, started, prepared.candles)
            return FetchResult(
                symbol=symbol,
                candles=prepared.candles,
                quality_report=prepared.quality_report,
            )
        except DataQualityError as error:
            _log_history_failure(symbol, interval, started, "data-quality error")
            return FetchResult(
                symbol=symbol,
                error=f"Yahoo Finance data-quality error: {error}",
                quality_report=error.quality_report,
            )
        except Exception as error:  # yfinance emits several transport exception types
            _log_history_failure(symbol, interval, started, "provider error")
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


def _log_history_success(
    symbol: str,
    interval: str,
    started: float,
    candles: pd.DataFrame,
) -> None:
    range_start, range_end = _opened_range(candles)
    LOGGER.info(
        "provider_history symbol=%s interval=%s rows=%s duration_ms=%.2f "
        "range_start=%s range_end=%s",
        symbol,
        interval,
        len(candles),
        _elapsed_ms(started),
        range_start,
        range_end,
    )


def _log_history_failure(symbol: str, interval: str, started: float, reason: str) -> None:
    LOGGER.warning(
        "provider_history_failed symbol=%s interval=%s duration_ms=%.2f reason=%s",
        symbol,
        interval,
        _elapsed_ms(started),
        reason,
    )


def _opened_range(candles: pd.DataFrame) -> tuple[str, str]:
    opened = pd.to_datetime(candles["opened_at_utc"], utc=True)
    return opened.min().isoformat(), opened.max().isoformat()


def _elapsed_ms(started: float) -> float:
    return (perf_counter() - started) * 1_000


def _normalize_column(value: object) -> str:
    return str(value).strip().lower()


def _normalize_symbol(value: object) -> str:
    return str(value).strip().upper()
