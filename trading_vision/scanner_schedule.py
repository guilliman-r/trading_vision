"""Pure due-job and wake-time calculations for the scanner."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from trading_vision.bist_intervals import (
    bist_intraday_close,
    bist_intraday_opens,
    latest_completed_intraday_open,
)
from trading_vision.data_quality import INTERVAL_LENGTHS
from trading_vision.market_calendar import ISTANBUL, BistSessionCalendar


def is_job_due(
    latest_candle_at: datetime | None,
    interval: str,
    now: datetime,
    provider_delay_seconds: int,
    calendar: BistSessionCalendar,
) -> bool:
    if latest_candle_at is None:
        return True
    expected = expected_latest_open(interval, now, provider_delay_seconds, calendar)
    if interval == "1d":
        latest_date = latest_candle_at.astimezone(ISTANBUL).date()
        return latest_date < expected.date()
    return latest_candle_at.astimezone(UTC) < expected.astimezone(UTC)


def expected_latest_open(
    interval: str,
    now: datetime,
    provider_delay_seconds: int,
    calendar: BistSessionCalendar,
) -> datetime:
    _validate_interval(interval)
    effective = now - timedelta(seconds=provider_delay_seconds)
    if interval == "1d":
        session = calendar.latest_completed_session(now, provider_delay_seconds)
        return datetime.combine(session.trading_date, datetime.min.time(), ISTANBUL)

    local_effective = effective.astimezone(ISTANBUL)
    current = calendar.session_for(local_effective.date())
    if current:
        latest = latest_completed_intraday_open(current, interval, local_effective)
        if latest is not None:
            return latest
    previous = calendar.latest_completed_session(now, provider_delay_seconds)
    return bist_intraday_opens(previous, interval)[-1]


def next_poll_at(
    now: datetime,
    intervals: tuple[str, ...],
    provider_delay_seconds: int,
    calendar: BistSessionCalendar,
) -> datetime:
    candidates = [
        _next_interval_poll(now, interval, provider_delay_seconds, calendar)
        for interval in intervals
    ]
    return min(candidates).astimezone(UTC)


def _next_interval_poll(
    now: datetime,
    interval: str,
    provider_delay_seconds: int,
    calendar: BistSessionCalendar,
) -> datetime:
    _validate_interval(interval)
    delay = timedelta(seconds=provider_delay_seconds)
    local_now = now.astimezone(ISTANBUL)
    for session in calendar.sessions_on_or_after(local_now.date()):
        if interval == "1d":
            candidate = session.closes_at + delay
            if candidate > local_now:
                return candidate
            continue
        for opened_at in bist_intraday_opens(session, interval):
            candidate = bist_intraday_close(opened_at, session, interval) + delay
            if candidate > local_now:
                return candidate
    raise RuntimeError("Unable to calculate the next scanner wake time")


def _duration(interval: str) -> timedelta:
    return INTERVAL_LENGTHS[interval].to_pytimedelta()


def _validate_interval(interval: str) -> None:
    if interval not in INTERVAL_LENGTHS:
        raise ValueError(f"Unsupported interval: {interval}")
