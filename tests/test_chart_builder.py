import pandas as pd

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
