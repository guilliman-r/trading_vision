"""Mark BIST candles complete from exchange sessions and provider delay."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

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
    expected = expected_latest_open(interval, now, provider_delay_seconds, session_calendar)
    opened_at = pd.to_datetime(candles["opened_at_utc"], utc=True)
    prepared = candles.copy()
    if interval == "1d":
        expected_date = expected.astimezone(ISTANBUL).date()
        prepared["is_complete"] = opened_at.dt.tz_convert(ISTANBUL).dt.date <= expected_date
    else:
        prepared["is_complete"] = opened_at <= expected.astimezone(UTC)
    return prepared
