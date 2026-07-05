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
    assert "Open 11.00" in figure.data[0].hovertext[1]
    assert "High 13.00" in figure.data[0].hovertext[1]
    assert "Low 10.00" in figure.data[0].hovertext[1]
    assert "Close 12.00" in figure.data[0].hovertext[1]
    assert "Change +1.00 (+9.09%)" in figure.data[0].hovertext[1]
    assert "Volume 150" in figure.data[0].hovertext[1]


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


def test_triangle_renders_converging_upper_and_lower_boundaries() -> None:
    times = pd.date_range("2025-01-01", periods=8, freq="D", tz="UTC")
    candles = pd.DataFrame(
        {
            "opened_at_utc": times,
            "open": [10] * 8,
            "high": [12] * 8,
            "low": [8] * 8,
            "close": [10] * 8,
            "volume": [100] * 8,
        }
    )
    points = (
        PatternPoint("upper_touch_1", 1, times[1].to_pydatetime(), 12),
        PatternPoint("lower_touch_1", 2, times[2].to_pydatetime(), 8),
        PatternPoint("upper_touch_2", 4, times[4].to_pydatetime(), 11),
        PatternPoint("lower_touch_2", 5, times[5].to_pydatetime(), 9),
        PatternPoint("apex", 7, times[7].to_pydatetime(), 10),
    )
    pattern = PatternMatch(
        pattern_type="symmetrical_triangle",
        direction="neutral",
        state="forming",
        started_at=times[1].to_pydatetime(),
        ended_at=None,
        confirmed_at=None,
        score=70,
        boundary_price=11,
        target_price=None,
        invalidation_price=None,
        points=points,
        reasons=("converging boundaries",),
        parameters={},
        detector_version="test-v1",
    )
    figure = build_chart(candles, "TEST", "1d", (pattern,))
    upper = next(trace for trace in figure.data if trace.name == "symmetrical_triangle · forming")
    lower = next(trace for trace in figure.data if trace.name == "Triangle lower boundary")
    apex = next(trace for trace in figure.data if trace.name == "Apex")
    assert upper.y[1] < upper.y[0]
    assert lower.y[1] > lower.y[0]
    assert upper.y[1] - lower.y[1] < upper.y[0] - lower.y[0]
    assert apex.y[0] == 10


def test_confirmed_triangle_boundaries_stop_at_confirmation() -> None:
    times = pd.date_range("2025-01-01", periods=100, freq="D", tz="UTC")
    candles = pd.DataFrame(
        {
            "opened_at_utc": times,
            "open": [300] * 100,
            "high": [310] * 100,
            "low": [290] * 100,
            "close": [305] * 100,
            "volume": [100] * 100,
        }
    )
    confirmation_index = 20
    points = (
        PatternPoint("upper_touch_1", 5, times[5].to_pydatetime(), 320),
        PatternPoint("lower_touch_1", 6, times[6].to_pydatetime(), 260),
        PatternPoint("upper_touch_2", 10, times[10].to_pydatetime(), 315),
        PatternPoint("lower_touch_2", 11, times[11].to_pydatetime(), 280),
        PatternPoint(
            "confirmation",
            confirmation_index,
            times[confirmation_index].to_pydatetime(),
            325,
        ),
    )
    pattern = PatternMatch(
        pattern_type="ascending_triangle",
        direction="bullish",
        state="confirmed",
        started_at=times[5].to_pydatetime(),
        ended_at=None,
        confirmed_at=times[confirmation_index].to_pydatetime(),
        score=85,
        boundary_price=315,
        target_price=1_000,
        invalidation_price=250,
        points=points,
        reasons=("steep lower boundary",),
        parameters={},
        detector_version="test-v1",
    )

    figure = build_chart(candles, "TEST", "1d", (pattern,))
    upper = next(trace for trace in figure.data if trace.name == "ascending_triangle · confirmed")
    lower = next(trace for trace in figure.data if trace.name == "Triangle lower boundary")
    target = next(trace for trace in figure.data if trace.name == "Target")

    assert upper.x[-1] == times[confirmation_index]
    assert lower.x[-1] == times[confirmation_index]
    assert lower.y[-1] == 316
    assert target.x[0] == times[confirmation_index]
    assert tuple(figure.layout.yaxis.range) == (288.8, 311.2)


def test_chart_opens_on_the_most_recent_candles() -> None:
    times = pd.date_range("2025-01-01", periods=250, freq="D", tz="UTC")
    candles = pd.DataFrame(
        {
            "opened_at_utc": times,
            "open": [100] * 250,
            "high": [105] * 250,
            "low": [95] * 250,
            "close": [102] * 250,
            "volume": [100] * 250,
        }
    )

    figure = build_chart(candles, "TEST", "1d")

    assert figure.layout.xaxis.range[0] == times[70]
    assert figure.layout.xaxis.range[1] == times[-1]
