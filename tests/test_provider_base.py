from __future__ import annotations

import pandas as pd

from trading_vision.providers.base import FetchResult, MarketDataProvider


class FixtureProvider(MarketDataProvider):
    name = "fixture"

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        return FetchResult(
            symbol=symbol,
            candles=pd.DataFrame({"close": [10.0]}),
        )


def test_market_data_provider_contract_has_safe_validation_default() -> None:
    provider = FixtureProvider()

    valid = provider.validate_symbol(" thyao.is ")
    invalid = provider.validate_symbol(" ")

    assert valid.succeeded
    assert valid.symbol == "THYAO.IS"
    assert not invalid.succeeded
    assert invalid.error == "Symbol is required"


def test_market_data_provider_contract_has_lightweight_metadata_default() -> None:
    metadata = FixtureProvider().fetch_metadata(" aapl ")

    assert metadata.succeeded
    assert metadata.symbol == "AAPL"
    assert metadata.provider_name == "fixture"
    assert metadata.name is None
    assert metadata.exchange is None
    assert metadata.currency is None


def test_fetch_result_success_requires_candles_and_no_error() -> None:
    assert FetchResult(symbol="AAPL", candles=pd.DataFrame({"close": [10.0]})).succeeded
    assert not FetchResult(symbol="AAPL").succeeded
    assert not FetchResult(
        symbol="AAPL",
        candles=pd.DataFrame({"close": [10.0]}),
        error="failed",
    ).succeeded


def test_batch_fetch_default_falls_back_to_single_symbol_fetches() -> None:
    results = FixtureProvider().fetch_history_batch(("AAPL", "MSFT"), "1d", batch_size=25)

    assert set(results) == {"AAPL", "MSFT"}
    assert all(result.succeeded for result in results.values())
