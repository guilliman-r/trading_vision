import pandas as pd

from trading_vision.models import PatternMatch, PatternPoint
from trading_vision.ui.chart_builder import build_chart, empty_chart


def test_empty_chart_has_message() -> None:
    figure = empty_chart("Nothing here")
    assert figure.layout.annotations[0].text == "Nothing here"


def test_chart_contains_candles_and_volume() -> None:
    candles = pd.DataFrame(
        {
            "opened_at_utc": pd.to_datetime(["2025-01-01", "2025-01-02"], utc=True),
            "open": [10, 11],
            "high": [12, 13],
            "low": [9, 10],
            "close": [11, 12],
            "volume": [100, 150],
        }
    )
    figure = build_chart(candles, "TEST", "1d")
    assert [trace.type for trace in figure.data] == ["candlestick", "bar"]
    assert figure.layout.uirevision == "TEST:1d"


def test_chart_renders_pattern_level_touches_confirmation_and_risk_lines() -> None:
    times = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"], utc=True)
    candles = pd.DataFrame(
        {
            "opened_at_utc": times,
            "open": [10, 11, 12],
            "high": [12, 13, 15],
            "low": [9, 10, 11],
            "close": [11, 12, 14],
            "volume": [100, 150, 300],
        }
    )
    pattern = PatternMatch(
        pattern_type="resistance_breakout",
        direction="bullish",
        state="confirmed",
        started_at=times[0].to_pydatetime(),
        ended_at=None,
        confirmed_at=times[2].to_pydatetime(),
        score=85,
        boundary_price=12,
        target_price=15,
        invalidation_price=11,
        points=(
            PatternPoint("touch_1", 0, times[0].to_pydatetime(), 12),
            PatternPoint("touch_2", 1, times[1].to_pydatetime(), 12.1),
            PatternPoint("confirmation", 2, times[2].to_pydatetime(), 14),
        ),
        reasons=("+35 tight level",),
        parameters={},
        detector_version="test-v1",
    )
    figure = build_chart(candles, "TEST", "1d", (pattern,))
    names = [trace.name for trace in figure.data]
    assert "resistance_breakout · confirmed" in names
    assert "Pattern structure" in names
    assert "Confirmation" in names
    assert "Target" in names
    assert "Invalidation" in names


def test_head_shoulders_boundary_uses_neckline_slope() -> None:
    times = pd.date_range("2025-01-01", periods=7, freq="D", tz="UTC")
    candles = pd.DataFrame(
        {
            "opened_at_utc": times,
            "open": [10, 12, 11, 15, 12, 13, 10],
            "high": [11, 14, 12, 17, 13, 15, 11],
            "low": [9, 11, 10, 14, 11, 12, 9],
            "close": [10, 13, 11, 16, 12, 14, 10],
            "volume": [100] * 7,
        }
    )
    points = (
        PatternPoint("left_shoulder", 1, times[1].to_pydatetime(), 14),
        PatternPoint("neckline_low_1", 2, times[2].to_pydatetime(), 10),
        PatternPoint("head", 3, times[3].to_pydatetime(), 17),
        PatternPoint("neckline_low_2", 4, times[4].to_pydatetime(), 11),
        PatternPoint("right_shoulder", 5, times[5].to_pydatetime(), 15),
    )
    pattern = PatternMatch(
        pattern_type="head_shoulders",
        direction="bearish",
        state="forming",
        started_at=times[1].to_pydatetime(),
        ended_at=None,
        confirmed_at=None,
        score=75,
        boundary_price=12,
        target_price=7,
        invalidation_price=17,
        points=points,
        reasons=("sloped neckline",),
        parameters={},
        detector_version="test-v1",
    )
    figure = build_chart(candles, "TEST", "1d", (pattern,))
    boundary = next(trace for trace in figure.data if trace.name == "head_shoulders · forming")
    assert boundary.y[0] == 10
    assert boundary.y[1] > boundary.y[0]
