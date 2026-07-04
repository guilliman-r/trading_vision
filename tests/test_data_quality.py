import pandas as pd
import pytest

from trading_vision.data_quality import prepare_candles


def test_prepare_candles_normalizes_and_sorts() -> None:
    frame = pd.DataFrame(
        {
            "open": [11, 10],
            "high": [12, 11],
            "low": [10, 9],
            "close": [11.5, 10.5],
            "volume": [200, 100],
        },
        index=pd.to_datetime(["2025-01-02", "2025-01-01"], utc=True),
    )
    result = prepare_candles(frame, "1d", "fixture")
    assert result.iloc[0]["open"] == 10
    assert result["is_complete"].all()
    assert result["source"].unique().tolist() == ["fixture"]


def test_prepare_candles_accepts_provider_named_datetime_index() -> None:
    frame = pd.DataFrame(
        {"open": [10], "high": [12], "low": [9], "close": [11], "volume": [100]},
        index=pd.to_datetime(["2025-01-01"], utc=True),
    )
    frame.index.name = "opened_at_utc"
    result = prepare_candles(frame, "1d", "fixture")
    assert result.iloc[0]["close"] == 11


def test_prepare_candles_rejects_invalid_ohlc() -> None:
    frame = pd.DataFrame(
        {"open": [10], "high": [9], "low": [8], "close": [10], "volume": [100]},
        index=pd.to_datetime(["2025-01-01"], utc=True),
    )
    with pytest.raises(ValueError, match="no valid candles"):
        prepare_candles(frame, "1d", "fixture")
