from __future__ import annotations

import pandas as pd

from trading_vision.patterns.pivots import PivotSettings, find_confirmed_pivots


def pivot_fixture(length: int = 30) -> pd.DataFrame:
    closes = [10.0 + (index % 4) * 0.05 for index in range(length)]
    frame = pd.DataFrame(
        {
            "opened_at_utc": pd.date_range("2025-01-01", periods=length, freq="D", tz="UTC"),
            "open": closes,
            "high": [close + 1 for close in closes],
            "low": [close - 1 for close in closes],
            "close": closes,
            "volume": [100.0] * length,
            "is_complete": [True] * length,
        }
    )
    frame.loc[15, ["open", "high", "low", "close"]] = [14.0, 18.0, 13.0, 15.0]
    return frame


def test_pivot_records_occurrence_and_confirmation_candles() -> None:
    settings = PivotSettings(
        left_bars=2,
        right_bars=2,
        atr_period=3,
        minimum_prominence_atr=0.2,
        minimum_prominence_percent=0.2,
    )
    pivots = find_confirmed_pivots(pivot_fixture(), settings)
    peak = next(pivot for pivot in pivots if pivot.index == 15 and pivot.kind == "high")
    assert peak.confirmation_index == 17
    assert peak.confirmed_at == pivot_fixture().loc[17, "opened_at_utc"].to_pydatetime()
    assert peak.prominence_atr > 0


def test_confirmed_pivots_do_not_change_when_unknowable_future_is_removed() -> None:
    settings = PivotSettings(
        left_bars=2,
        right_bars=2,
        atr_period=3,
        minimum_prominence_atr=0.2,
        minimum_prominence_percent=0.2,
    )
    frame = pivot_fixture()
    full = find_confirmed_pivots(frame, settings)
    cutoff_index = 20
    truncated = find_confirmed_pivots(frame.iloc[: cutoff_index + 1], settings)
    knowable = [pivot for pivot in full if pivot.confirmation_index <= cutoff_index]
    assert truncated == knowable
