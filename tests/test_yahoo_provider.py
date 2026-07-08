from __future__ import annotations

import logging

import pandas as pd
import pytest

from trading_vision.providers import yahoo
from trading_vision.providers.yahoo import (
    YahooFinanceProvider,
    classify_yahoo_failure,
    normalize_yahoo_history_frame,
)


def test_normalizes_single_symbol_yahoo_history_shape() -> None:
    raw = pd.DataFrame(
        {
            "Open": [10.0],
            "High": [11.0],
            "Low": [9.5],
            "Close": [10.5],
            "Volume": [1_000],
        },
        index=pd.to_datetime(["2026-07-06 10:00"], utc=False),
    )

    normalized = normalize_yahoo_history_frame(raw, "THYAO.IS")

    assert list(normalized.columns) == ["open", "high", "low", "close", "volume"]
    assert normalized.index.name == "opened_at_utc"
    assert str(normalized.index.tz) == "UTC"


def test_normalizes_price_first_multi_symbol_yahoo_history_shape() -> None:
    columns = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Volume"], ["THYAO.IS", "GARAN.IS"]],
        names=["Price", "Ticker"],
    )
    raw = pd.DataFrame([[10, 20, 11, 21, 9, 19, 10.5, 20.5, 1_000, 2_000]], columns=columns)

    normalized = normalize_yahoo_history_frame(raw, "THYAO.IS")

    assert normalized.iloc[0].to_dict() == {
        "open": 10,
        "high": 11,
        "low": 9,
        "close": 10.5,
        "volume": 1_000,
    }


def test_normalizes_ticker_first_multi_symbol_yahoo_history_shape() -> None:
    columns = pd.MultiIndex.from_product(
        [["THYAO.IS", "GARAN.IS"], ["Open", "High", "Low", "Close", "Volume"]],
        names=["Ticker", "Price"],
    )
    raw = pd.DataFrame([[10, 11, 9, 10.5, 1_000, 20, 21, 19, 20.5, 2_000]], columns=columns)

    normalized = normalize_yahoo_history_frame(raw, "GARAN.IS")

    assert normalized.iloc[0].to_dict() == {
        "open": 20,
        "high": 21,
        "low": 19,
        "close": 20.5,
        "volume": 2_000,
    }


def test_multi_symbol_yahoo_history_requires_a_symbol_choice() -> None:
    columns = pd.MultiIndex.from_product(
        [["THYAO.IS", "GARAN.IS"], ["Open", "High", "Low", "Close", "Volume"]]
    )
    raw = pd.DataFrame([[10, 11, 9, 10.5, 1_000, 20, 21, 19, 20.5, 2_000]], columns=columns)

    with pytest.raises(ValueError, match="requires a symbol"):
        normalize_yahoo_history_frame(raw)


def test_fetch_history_logs_duration_and_returned_candle_range(monkeypatch, caplog) -> None:
    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def history(self, **kwargs) -> pd.DataFrame:
            assert self.symbol == "THYAO.IS"
            assert kwargs == {
                "period": "2y",
                "interval": "1d",
                "auto_adjust": True,
                "actions": False,
            }
            return pd.DataFrame(
                {
                    "Open": [10.0, 11.0],
                    "High": [12.0, 13.0],
                    "Low": [9.0, 10.0],
                    "Close": [11.0, 12.0],
                    "Volume": [100.0, 150.0],
                },
                index=pd.to_datetime(["2026-07-01", "2026-07-02"], utc=True),
            )

    monkeypatch.setattr(yahoo.yf, "Ticker", FakeTicker)
    caplog.set_level(logging.INFO, logger="trading_vision.providers.yahoo")

    result = YahooFinanceProvider().fetch_history("THYAO.IS", "1d")

    assert result.succeeded
    assert "provider_history symbol=THYAO.IS interval=1d rows=2" in caplog.text
    assert "duration_ms=" in caplog.text
    assert "range_start=2026-07-01T00:00:00+00:00" in caplog.text
    assert "range_end=2026-07-02T00:00:00+00:00" in caplog.text


def test_fetch_history_classifies_unsupported_interval() -> None:
    result = YahooFinanceProvider().fetch_history("THYAO.IS", "3h")

    assert not result.succeeded
    assert result.failure_kind == "unsupported_interval"
    assert result.error == "Unsupported interval: 3h"


def test_fetch_history_classifies_blank_symbol_as_invalid_ticker() -> None:
    result = YahooFinanceProvider().fetch_history(" ", "1d")

    assert not result.succeeded
    assert result.failure_kind == "invalid_ticker"
    assert result.error == "Yahoo Finance invalid ticker: symbol is required"


def test_fetch_history_classifies_empty_history(monkeypatch) -> None:
    class EmptyTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def history(self, **kwargs) -> pd.DataFrame:
            return pd.DataFrame()

    monkeypatch.setattr(yahoo.yf, "Ticker", EmptyTicker)

    result = YahooFinanceProvider().fetch_history("THYAO.IS", "1d")

    assert not result.succeeded
    assert result.failure_kind == "empty_history"
    assert result.error == "Yahoo Finance returned no candles"


def test_fetch_history_classifies_rate_limits(monkeypatch) -> None:
    class RateLimitedTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def history(self, **kwargs) -> pd.DataFrame:
            raise RuntimeError("Too Many Requests: rate limit 429")

    monkeypatch.setattr(yahoo.yf, "Ticker", RateLimitedTicker)
    provider = YahooFinanceProvider(max_attempts=1)

    result = provider.fetch_history("THYAO.IS", "1d")

    assert not result.succeeded
    assert result.failure_kind == "rate_limited"
    assert result.error == "Yahoo Finance rate limit: Too Many Requests: rate limit 429"


def test_fetch_history_batch_uses_yfinance_download_chunks(monkeypatch) -> None:
    calls = []

    def fake_download(**kwargs) -> pd.DataFrame:
        symbols = kwargs["tickers"]
        calls.append((tuple(symbols), kwargs))
        columns = pd.MultiIndex.from_product(
            [symbols, ["Open", "High", "Low", "Close", "Volume"]],
            names=["Ticker", "Price"],
        )
        values = []
        for index, _symbol in enumerate(symbols, start=1):
            values.extend([10.0 + index, 12.0 + index, 9.0 + index, 11.0 + index, 100.0])
        return pd.DataFrame([values], columns=columns, index=pd.to_datetime(["2026-07-01"]))

    monkeypatch.setattr(yahoo.yf, "download", fake_download)
    provider = YahooFinanceProvider()

    results = provider.fetch_history_batch(
        ["THYAO.IS", "GARAN.IS", "ASELS.IS"],
        "1d",
        batch_size=2,
    )

    assert list(results) == ["THYAO.IS", "GARAN.IS", "ASELS.IS"]
    assert all(result.succeeded for result in results.values())
    assert [call[0] for call in calls] == [("THYAO.IS", "GARAN.IS"), ("ASELS.IS",)]
    first_call = calls[0][1]
    assert first_call["period"] == "2y"
    assert first_call["interval"] == "1d"
    assert first_call["auto_adjust"] is True
    assert first_call["actions"] is False
    assert first_call["progress"] is False
    assert first_call["group_by"] == "ticker"


def test_fetch_history_batch_marks_missing_symbols_as_partial_failures(monkeypatch) -> None:
    def fake_download(**kwargs) -> pd.DataFrame:
        columns = pd.MultiIndex.from_product(
            [["THYAO.IS"], ["Open", "High", "Low", "Close", "Volume"]],
            names=["Ticker", "Price"],
        )
        return pd.DataFrame(
            [[10.0, 12.0, 9.0, 11.0, 100.0]],
            columns=columns,
            index=pd.to_datetime(["2026-07-01"]),
        )

    monkeypatch.setattr(yahoo.yf, "download", fake_download)

    results = YahooFinanceProvider().fetch_history_batch(["THYAO.IS", "GARAN.IS"], "1d", 10)

    assert results["THYAO.IS"].succeeded
    assert not results["GARAN.IS"].succeeded
    assert results["GARAN.IS"].failure_kind == "partial_batch_failure"


def test_fetch_history_retries_provider_errors_with_bounded_backoff(monkeypatch) -> None:
    attempts = []

    class FlakyTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def history(self, **kwargs) -> pd.DataFrame:
            attempts.append((self.symbol, kwargs))
            if len(attempts) < 3:
                raise TimeoutError("temporary timeout")
            return pd.DataFrame(
                {
                    "Open": [10.0],
                    "High": [12.0],
                    "Low": [9.0],
                    "Close": [11.0],
                    "Volume": [100.0],
                },
                index=pd.to_datetime(["2026-07-01"], utc=True),
            )

    waits = []
    monkeypatch.setattr(yahoo.yf, "Ticker", FlakyTicker)
    provider = YahooFinanceProvider(
        base_retry_delay_seconds=1.0,
        max_retry_delay_seconds=3.0,
        sleeper=waits.append,
        jitter=lambda _low, _high: 0.25,
    )

    result = provider.fetch_history("THYAO.IS", "1d")

    assert result.succeeded
    assert len(attempts) == 3
    assert waits == [1.25, 2.25]


def test_fetch_history_stops_after_max_retry_attempts(monkeypatch) -> None:
    attempts = []

    class BrokenTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def history(self, **kwargs) -> pd.DataFrame:
            attempts.append((self.symbol, kwargs))
            raise TimeoutError("still down")

    waits = []
    monkeypatch.setattr(yahoo.yf, "Ticker", BrokenTicker)
    provider = YahooFinanceProvider(
        max_attempts=2,
        base_retry_delay_seconds=1.0,
        sleeper=waits.append,
        jitter=lambda _low, _high: 0.0,
    )

    result = provider.fetch_history("THYAO.IS", "1d")

    assert not result.succeeded
    assert result.failure_kind == "timeout"
    assert result.error == "Yahoo Finance timeout: still down"
    assert len(attempts) == 2
    assert waits == [1.0]


def test_fetch_history_rejects_unbounded_retry_attempts() -> None:
    with pytest.raises(ValueError, match="at most 5"):
        YahooFinanceProvider(max_attempts=6)


def test_yahoo_failure_classifier_recognizes_invalid_and_partial_batch_errors() -> None:
    assert classify_yahoo_failure(RuntimeError("No timezone found, symbol may be delisted")) == (
        "invalid_ticker"
    )
    assert classify_yahoo_failure(RuntimeError("partial batch failure: GARAN.IS failed")) == (
        "partial_batch_failure"
    )
    assert classify_yahoo_failure(RuntimeError("Yahoo data did not contain symbol: GARAN.IS")) == (
        "partial_batch_failure"
    )
