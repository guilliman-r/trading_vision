from __future__ import annotations

from datetime import date

import pandas as pd

from trading_vision.market_calendar import ISTANBUL, BistSessionCalendar
from trading_vision.ui.chart_builder import build_chart
from trading_vision.ui.range_breaks import bist_range_breaks


def _candles(times: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "opened_at_utc": times,
            "open": [100] * len(times),
            "high": [105] * len(times),
            "low": [95] * len(times),
            "close": [102] * len(times),
            "volume": [1_000] * len(times),
        }
    )


def _local_midnights(*days: str) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(days).tz_localize(ISTANBUL).tz_convert("UTC")


def test_daily_breaks_include_weekends_and_calendar_holidays() -> None:
    candles = _candles(_local_midnights("2026-07-03", "2026-07-16"))

    breaks = bist_range_breaks(candles, "1d", BistSessionCalendar())
    closed_dates = {
        pd.Timestamp(value).astimezone(ISTANBUL).date() for value in breaks[0]["values"]
    }

    assert date(2026, 7, 4) in closed_dates
    assert date(2026, 7, 5) in closed_dates
    assert date(2026, 7, 15) in closed_dates
    assert date(2026, 7, 6) not in closed_dates


def test_intraday_breaks_hide_overnight_and_half_day_remainder() -> None:
    times = pd.date_range("2026-05-25 07:00", "2026-05-27 15:00", freq="1h", tz="UTC")
    candles = _candles(times)

    breaks = bist_range_breaks(candles, "1h", BistSessionCalendar())
    overnight = next(item for item in breaks if item.get("pattern") == "hour")
    half_days = next(
        item for item in breaks if item.get("dvalue") == 3_600_000 and "values" in item
    )
    half_day_times = [pd.Timestamp(value).astimezone(ISTANBUL) for value in half_days["values"]]

    assert overnight["bounds"] == [15, 7]
    assert half_day_times[0].date() == date(2026, 5, 26)
    assert (half_day_times[0].hour, half_day_times[0].minute) == (12, 30)


def test_chart_applies_range_breaks_only_when_symbol_is_bist() -> None:
    candles = _candles(_local_midnights("2026-07-03", "2026-07-06"))

    generic = build_chart(candles, "AAPL", "1d", is_bist=False)
    bist = build_chart(candles, "THYAO.IS", "1d", is_bist=True)

    assert not generic.layout.xaxis.rangebreaks
    assert bist.layout.xaxis.rangebreaks
    assert bist.layout.xaxis2.rangebreaks == bist.layout.xaxis.rangebreaks
