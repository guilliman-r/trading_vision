from __future__ import annotations

import pandas as pd
import pytest

from trading_vision.providers.yahoo import normalize_yahoo_history_frame


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
