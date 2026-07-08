from __future__ import annotations

import os

import pytest

from trading_vision.providers.yahoo import YahooFinanceProvider

pytestmark = pytest.mark.skipif(
    os.getenv("TV_RUN_LIVE_PROVIDER_TESTS") != "1",
    reason="Set TV_RUN_LIVE_PROVIDER_TESTS=1 to call Yahoo Finance",
)


@pytest.mark.parametrize(
    ("symbol", "interval"),
    (
        ("THYAO.IS", "1d"),
        ("AAPL", "1d"),
    ),
)
def test_live_yahoo_history_for_representative_symbols(symbol: str, interval: str) -> None:
    result = YahooFinanceProvider(max_attempts=1).fetch_history(symbol, interval)

    assert result.succeeded, result.error
    assert not result.candles.empty
    assert {"opened_at_utc", "open", "high", "low", "close", "volume"}.issubset(
        result.candles.columns
    )
