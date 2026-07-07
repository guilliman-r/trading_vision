"""Yahoo Finance adapter; all yfinance-specific behavior stays here."""

from __future__ import annotations

import logging
import random
from collections.abc import Callable
from time import perf_counter, sleep

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

    def __init__(
        self,
        max_attempts: int = 3,
        base_retry_delay_seconds: float = 0.5,
        max_retry_delay_seconds: float = 5.0,
        sleeper: Callable[[float], None] = sleep,
        jitter: Callable[[float, float], float] = random.uniform,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.max_attempts = max_attempts
        self.base_retry_delay_seconds = base_retry_delay_seconds
        self.max_retry_delay_seconds = max_retry_delay_seconds
        self.sleeper = sleeper
        self.jitter = jitter

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        if not symbol.strip():
            return FetchResult(
                symbol=symbol,
                error="Yahoo Finance invalid ticker: symbol is required",
                failure_kind="invalid_ticker",
            )
        if interval not in PERIOD_BY_INTERVAL:
            return FetchResult(
                symbol=symbol,
                error=f"Unsupported interval: {interval}",
                failure_kind="unsupported_interval",
            )
        started = perf_counter()
        try:
            raw = self._download_history(symbol, interval)
            if raw.empty:
                failure_kind = "empty_history"
                _log_history_failure(symbol, interval, started, failure_kind)
                return FetchResult(
                    symbol=symbol,
                    error="Yahoo Finance returned no candles",
                    failure_kind=failure_kind,
                )
            normalized = normalize_yahoo_history_frame(raw, symbol)
            prepared = prepare_candles_with_report(normalized, interval, self.name)
            _log_history_success(symbol, interval, started, prepared.candles)
            return FetchResult(
                symbol=symbol,
                candles=prepared.candles,
                quality_report=prepared.quality_report,
            )
        except DataQualityError as error:
            failure_kind = "data_quality"
            _log_history_failure(symbol, interval, started, failure_kind)
            return FetchResult(
                symbol=symbol,
                error=f"Yahoo Finance data-quality error: {error}",
                quality_report=error.quality_report,
                failure_kind=failure_kind,
            )
        except Exception as error:  # yfinance emits several transport exception types
            failure_kind = classify_yahoo_failure(error)
            _log_history_failure(symbol, interval, started, failure_kind)
            return FetchResult(
                symbol=symbol,
                error=f"{_failure_title(failure_kind)}: {error}",
                failure_kind=failure_kind,
            )

    def _download_history(self, symbol: str, interval: str) -> pd.DataFrame:
        for attempt in range(1, self.max_attempts + 1):
            try:
                return yf.Ticker(symbol).history(
                    period=PERIOD_BY_INTERVAL[interval],
                    interval=interval,
                    auto_adjust=True,
                    actions=False,
                )
            except Exception:
                if attempt == self.max_attempts:
                    raise
                delay = self._retry_delay_seconds(attempt)
                LOGGER.warning(
                    "provider_history_retry symbol=%s interval=%s attempt=%s "
                    "next_delay_seconds=%.2f",
                    symbol,
                    interval,
                    attempt,
                    delay,
                )
                self.sleeper(delay)
        raise RuntimeError("Provider retry loop ended unexpectedly")

    def _retry_delay_seconds(self, attempt: int) -> float:
        base_delay = self.base_retry_delay_seconds * (2 ** (attempt - 1))
        capped_delay = min(base_delay, self.max_retry_delay_seconds)
        return capped_delay + self.jitter(0, capped_delay)


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


def classify_yahoo_failure(error: Exception) -> str:
    """Return a stable failure kind for common Yahoo/yfinance failures."""

    message = str(error).lower()
    error_name = error.__class__.__name__.lower()
    if "partial batch" in message or "partially failed" in message:
        return "partial_batch_failure"
    if "rate" in message and "limit" in message:
        return "rate_limited"
    if "too many requests" in message or "429" in message or "ratelimit" in error_name:
        return "rate_limited"
    if isinstance(error, TimeoutError) or "timeout" in message or "timed out" in message:
        return "timeout"
    if "invalid ticker" in message or "no timezone found" in message or "delisted" in message:
        return "invalid_ticker"
    return "provider_error"


def _failure_title(failure_kind: str) -> str:
    labels = {
        "invalid_ticker": "Yahoo Finance invalid ticker",
        "partial_batch_failure": "Yahoo Finance partial batch failure",
        "provider_error": "Yahoo Finance error",
        "rate_limited": "Yahoo Finance rate limit",
        "timeout": "Yahoo Finance timeout",
    }
    return labels.get(failure_kind, "Yahoo Finance error")


def _opened_range(candles: pd.DataFrame) -> tuple[str, str]:
    opened = pd.to_datetime(candles["opened_at_utc"], utc=True)
    return opened.min().isoformat(), opened.max().isoformat()


def _elapsed_ms(started: float) -> float:
    return (perf_counter() - started) * 1_000


def _normalize_column(value: object) -> str:
    return str(value).strip().lower()


def _normalize_symbol(value: object) -> str:
    return str(value).strip().upper()
