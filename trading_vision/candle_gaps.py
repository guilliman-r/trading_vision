"""Detect missing candles inside explicitly covered BIST sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

import pandas as pd

from trading_vision.data_quality import INTERVAL_LENGTHS
from trading_vision.market_calendar import ISTANBUL, BistSessionCalendar


@dataclass(frozen=True, slots=True)
class CandleGapReport:
    missing_at: tuple[datetime, ...] = ()

    @property
    def count(self) -> int:
        return len(self.missing_at)


def find_bist_candle_gaps(
    candles: pd.DataFrame,
    interval: str,
    calendar: BistSessionCalendar | None = None,
) -> CandleGapReport:
    """Find internal session gaps without inventing replacement candles."""

    if interval not in INTERVAL_LENGTHS:
        raise ValueError(f"Unsupported interval: {interval}")
    completed = candles.loc[candles["is_complete"]] if "is_complete" in candles else candles
    if completed.empty:
        return CandleGapReport()

    timestamps = pd.to_datetime(completed["opened_at_utc"], utc=True)
    session_calendar = calendar or BistSessionCalendar()
    if interval == "1d":
        missing = _daily_gaps(timestamps, session_calendar)
    else:
        missing = _intraday_gaps(timestamps, interval, session_calendar)
    return CandleGapReport(tuple(missing))


def _daily_gaps(
    timestamps: pd.Series,
    calendar: BistSessionCalendar,
) -> list[datetime]:
    actual_dates = {timestamp.tz_convert(ISTANBUL).date() for timestamp in timestamps}
    first_date, last_date = min(actual_dates), max(actual_dates)
    return [
        datetime.combine(day, time.min, ISTANBUL).astimezone(UTC)
        for day in _dates_between(first_date, last_date)
        if day.year in calendar.covered_years
        and calendar.session_for(day) is not None
        and day not in actual_dates
    ]


def _intraday_gaps(
    timestamps: pd.Series,
    interval: str,
    calendar: BistSessionCalendar,
) -> list[datetime]:
    actual = {timestamp.to_pydatetime().astimezone(UTC) for timestamp in timestamps}
    first, last = min(actual), max(actual)
    first_date = first.astimezone(ISTANBUL).date()
    last_date = last.astimezone(ISTANBUL).date()
    duration = INTERVAL_LENGTHS[interval].to_pytimedelta()
    missing: list[datetime] = []
    for day in _dates_between(first_date, last_date):
        if day.year not in calendar.covered_years:
            continue
        session = calendar.session_for(day)
        if session is None:
            continue
        expected = session.opens_at
        while expected + duration <= session.data_closes_at:
            expected_utc = expected.astimezone(UTC)
            if first <= expected_utc <= last and expected_utc not in actual:
                missing.append(expected_utc)
            expected += duration
    return missing


def _dates_between(first_date: date, last_date: date):
    current = first_date
    while current <= last_date:
        yield current
        current += timedelta(days=1)
