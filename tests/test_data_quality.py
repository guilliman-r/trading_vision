import pandas as pd
import pytest

from trading_vision.data_quality import (
    DataQualityError,
    prepare_candles,
    prepare_candles_with_report,
)


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
    with pytest.raises(DataQualityError, match="no valid candles") as captured:
        prepare_candles(frame, "1d", "fixture")
    assert captured.value.quality_report.quarantined_rows == 1
    assert captured.value.quality_report.issue_count("high_below_price") == 1


def test_prepare_candles_reports_clean_input() -> None:
    frame = pd.DataFrame(
        {"open": [10], "high": [12], "low": [9], "close": [11], "volume": [100]},
        index=pd.to_datetime(["2025-01-01"], utc=True),
    )

    prepared = prepare_candles_with_report(frame, "1d", "fixture")

    assert len(prepared.candles) == 1
    assert prepared.quality_report.input_rows == 1
    assert prepared.quality_report.valid_rows == 1
    assert not prepared.quality_report.has_warnings


def test_prepare_candles_quarantines_rows_with_reason_counts() -> None:
    frame = pd.DataFrame(
        {
            "open": [10, 11, 10, 10, 10],
            "high": [12, 13, 9, 12, 12],
            "low": [9, 10, 8, 9, 9],
            "close": [11, 12, 10, 11, 11],
            "volume": [100, 150, 100, -1, 100],
        },
        index=["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-03", "not-a-date"],
    )

    prepared = prepare_candles_with_report(frame, "1d", "fixture")
    report = prepared.quality_report

    assert len(prepared.candles) == 1
    assert report.quarantined_rows == 4
    assert report.issue_count("duplicate_timestamp") == 1
    assert report.issue_count("high_below_price") == 1
    assert report.issue_count("negative_volume") == 1
    assert report.issue_count("invalid_timestamp") == 1
    assert "Quarantined 4 of 5 provider rows" in report.summary()
