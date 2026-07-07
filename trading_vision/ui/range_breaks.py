"""Build Plotly axis breaks from the maintained BIST session calendar."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd

from trading_vision.data_quality import INTERVAL_LENGTHS
from trading_vision.market_calendar import ISTANBUL, BistSessionCalendar

MILLISECONDS_PER_DAY = 86_400_000
NORMAL_DATA_CLOSE = time(18, 0)


def bist_range_breaks(
    candles: pd.DataFrame,
    interval: str,
    calendar: BistSessionCalendar | None = None,
) -> list[dict[str, object]]:
    """Return closed-date, overnight, and half-day breaks for a BIST chart."""

    if candles.empty:
        return []
    if interval not in INTERVAL_LENGTHS:
        raise ValueError(f"Unsupported interval: {interval}")

    first_date, last_date = _local_date_range(candles)
    session_calendar = calendar or BistSessionCalendar()
    closed_dates = _closed_date_values(first_date, last_date, session_calendar)
    breaks: list[dict[str, object]] = []
    if closed_dates:
        breaks.append({"values": closed_dates, "dvalue": MILLISECONDS_PER_DAY})
    if interval == "1d":
        return breaks

    # Yahoo timestamps BIST hourly bars at xx:30, starting at 09:30 Istanbul.
    open_bound = 6.5 if interval == "1h" else 7
    breaks.append({"pattern": "hour", "bounds": [15, open_bound]})
    half_day_values = _half_day_values(first_date, last_date, interval, session_calendar)
    if half_day_values:
        duration_ms = int(INTERVAL_LENGTHS[interval].total_seconds() * 1_000)
        breaks.append({"values": half_day_values, "dvalue": duration_ms})
    return breaks


def _local_date_range(candles: pd.DataFrame) -> tuple[date, date]:
    timestamps = pd.to_datetime(candles["opened_at_utc"], utc=True).dt.tz_convert(ISTANBUL)
    return timestamps.iloc[0].date(), timestamps.iloc[-1].date()


def _closed_date_values(
    first_date: date,
    last_date: date,
    calendar: BistSessionCalendar,
) -> list[datetime]:
    return [
        datetime.combine(day, time.min, ISTANBUL)
        for day in _dates_between(first_date, last_date)
        if calendar.session_for(day) is None
    ]


def _half_day_values(
    first_date: date,
    last_date: date,
    interval: str,
    calendar: BistSessionCalendar,
) -> list[datetime]:
    values: list[datetime] = []
    duration = INTERVAL_LENGTHS[interval].to_pytimedelta()
    for day in _dates_between(first_date, last_date):
        session = calendar.session_for(day)
        if session is None or session.data_closes_at.time() >= NORMAL_DATA_CLOSE:
            continue
        normal_close = datetime.combine(day, NORMAL_DATA_CLOSE, ISTANBUL)
        current = session.data_closes_at
        while current < normal_close:
            values.append(current)
            current += duration
    return values


def _dates_between(first_date: date, last_date: date):
    current = first_date
    while current <= last_date:
        yield current
        current += timedelta(days=1)
