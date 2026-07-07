"""Mark BIST candles complete from exchange sessions and provider delay."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from trading_vision.bist_intervals import bist_intraday_close
from trading_vision.market_calendar import ISTANBUL, BistSessionCalendar
from trading_vision.scanner_schedule import expected_latest_open


def mark_bist_candle_completion(
    candles: pd.DataFrame,
    interval: str,
    now: datetime,
    provider_delay_seconds: int,
    calendar: BistSessionCalendar | None = None,
) -> pd.DataFrame:
    """Return a copy with completion flags derived from the BIST calendar."""

    if candles.empty:
        return candles.copy()
    session_calendar = calendar or BistSessionCalendar()
    opened_at = pd.to_datetime(candles["opened_at_utc"], utc=True)
    prepared = candles.copy()
    if interval == "1d":
        expected = expected_latest_open(interval, now, provider_delay_seconds, session_calendar)
        expected_date = expected.astimezone(ISTANBUL).date()
        prepared["is_complete"] = opened_at.dt.tz_convert(ISTANBUL).dt.date <= expected_date
    else:
        effective_time = now.astimezone(UTC) - timedelta(seconds=provider_delay_seconds)
        prepared["is_complete"] = [
            _intraday_is_complete(
                moment.to_pydatetime(),
                interval,
                effective_time,
                session_calendar,
            )
            for moment in opened_at
        ]
    return prepared


def _intraday_is_complete(
    opened_at: datetime,
    interval: str,
    effective_time: datetime,
    calendar: BistSessionCalendar,
) -> bool:
    local_open = opened_at.astimezone(ISTANBUL)
    session = calendar.session_for(local_open.date())
    if session is None:
        return False
    closes_at = bist_intraday_close(local_open, session, interval)
    return closes_at.astimezone(UTC) <= effective_time
