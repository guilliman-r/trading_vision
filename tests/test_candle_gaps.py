from __future__ import annotations

from datetime import date

import pandas as pd

from trading_vision.candle_gaps import find_bist_candle_gaps
from trading_vision.market_calendar import ISTANBUL, BistSessionCalendar


def _daily_candles(*days: str) -> pd.DataFrame:
    timestamps = pd.DatetimeIndex(days).tz_localize(ISTANBUL).tz_convert("UTC")
    return pd.DataFrame({"opened_at_utc": timestamps, "is_complete": True})


def test_daily_gap_detects_missing_session_but_not_weekend() -> None:
    candles = _daily_candles("2026-01-02", "2026-01-06")

    report = find_bist_candle_gaps(candles, "1d", BistSessionCalendar())
    missing_dates = [moment.astimezone(ISTANBUL).date() for moment in report.missing_at]

    assert missing_dates == [date(2026, 1, 5)]


def test_daily_gap_does_not_flag_configured_holiday() -> None:
    candles = _daily_candles("2026-07-14", "2026-07-16")

    report = find_bist_candle_gaps(candles, "1d", BistSessionCalendar())

    assert report.count == 0


def test_intraday_gap_finds_missing_completed_interval() -> None:
    timestamps = pd.to_datetime(
        ["2026-07-06 07:00", "2026-07-06 07:15", "2026-07-06 07:45"],
        utc=True,
    )
    candles = pd.DataFrame({"opened_at_utc": timestamps, "is_complete": True})

    report = find_bist_candle_gaps(candles, "15m", BistSessionCalendar())

    assert report.count == 1
    assert report.missing_at[0].astimezone(ISTANBUL).strftime("%H:%M") == "10:30"


def test_uncovered_calendar_year_does_not_create_false_gap() -> None:
    candles = _daily_candles("2025-01-02", "2025-01-06")

    report = find_bist_candle_gaps(candles, "1d", BistSessionCalendar())

    assert report.count == 0
