import pandas as pd
import pytest

from trading_vision.patterns.indicators import (
    average_true_range,
    crossed_boundary,
    fit_line,
    line_value,
    percent_distance,
    true_range,
)


def test_true_range_and_atr_are_explicit_rolling_calculations() -> None:
    candles = pd.DataFrame(
        {
            "high": [11.0, 13.0, 14.0],
            "low": [9.0, 10.0, 12.0],
            "close": [10.0, 12.0, 13.0],
        }
    )
    assert true_range(candles).tolist() == [2.0, 3.0, 2.0]
    atr = average_true_range(candles, period=2)
    assert pd.isna(atr.iloc[0])
    assert atr.iloc[1] == 2.5


def test_line_helpers_use_candle_index_units() -> None:
    slope, intercept = fit_line([0, 2, 4], [10.0, 12.0, 14.0])
    assert slope == pytest.approx(1.0)
    assert line_value(slope, intercept, 6) == pytest.approx(16.0)


def test_boundary_and_percent_helpers() -> None:
    assert percent_distance(100, 101) == pytest.approx(0.995, rel=1e-3)
    assert crossed_boundary(102, 100, 1, "above")
    assert crossed_boundary(98, 100, 1, "below")
