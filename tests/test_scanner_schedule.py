from __future__ import annotations

from datetime import UTC, datetime

from trading_vision.market_calendar import ISTANBUL, BistSessionCalendar
from trading_vision.scanner_schedule import expected_latest_open, is_job_due, next_poll_at


def test_calendar_applies_weekends_holidays_and_half_days() -> None:
    calendar = BistSessionCalendar()
    assert calendar.session_for(datetime(2026, 7, 4).date()) is None
    assert calendar.session_for(datetime(2026, 7, 15).date()) is None
    half_day = calendar.session_for(datetime(2026, 5, 26).date())
    assert half_day is not None
    assert half_day.data_closes_at.hour == 12
    assert half_day.data_closes_at.minute == 30


def test_istanbul_offset_is_stable_across_seasons() -> None:
    winter = datetime(2026, 1, 15, 12, tzinfo=ISTANBUL)
    summer = datetime(2026, 7, 15, 12, tzinfo=ISTANBUL)
    assert winter.utcoffset() == summer.utcoffset()


def test_daily_job_is_not_repolled_during_weekend() -> None:
    calendar = BistSessionCalendar()
    saturday = datetime(2026, 7, 4, 12, tzinfo=ISTANBUL)
    friday_candle = datetime(2026, 7, 3, 0, tzinfo=ISTANBUL)
    thursday_candle = datetime(2026, 7, 2, 0, tzinfo=ISTANBUL)
    assert not is_job_due(friday_candle, "1d", saturday, 60, calendar)
    assert is_job_due(thursday_candle, "1d", saturday, 60, calendar)


def test_intraday_job_becomes_due_after_completed_boundary_and_delay() -> None:
    calendar = BistSessionCalendar()
    monday = datetime(2026, 7, 6, 11, 1, tzinfo=ISTANBUL)
    expected = expected_latest_open("1h", monday, 60, calendar)
    assert expected == datetime(2026, 7, 6, 9, 30, tzinfo=ISTANBUL)
    assert is_job_due(datetime(2026, 7, 3, 17, 30, tzinfo=ISTANBUL), "1h", monday, 60, calendar)
    assert not is_job_due(expected, "1h", monday, 60, calendar)


def test_hourly_scanner_wakes_on_yahoo_bar_boundary() -> None:
    calendar = BistSessionCalendar()
    before_first_boundary = datetime(2026, 7, 6, 10, 15, tzinfo=ISTANBUL)

    next_hourly = next_poll_at(before_first_boundary, ("1h",), 60, calendar)

    assert next_hourly.astimezone(ISTANBUL) == datetime(
        2026, 7, 6, 10, 31, tzinfo=ISTANBUL
    )


def test_closed_market_wakes_at_next_relevant_boundary() -> None:
    calendar = BistSessionCalendar()
    saturday = datetime(2026, 7, 4, 12, tzinfo=ISTANBUL)
    next_intraday = next_poll_at(saturday, ("15m",), 60, calendar)
    next_daily = next_poll_at(saturday, ("1d",), 60, calendar)
    assert next_intraday.astimezone(ISTANBUL) == datetime(2026, 7, 6, 10, 16, tzinfo=ISTANBUL)
    assert next_daily.astimezone(ISTANBUL) == datetime(2026, 7, 6, 18, 11, tzinfo=ISTANBUL)
    assert next_intraday.tzinfo == UTC
