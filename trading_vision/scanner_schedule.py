"""Pure due-job and wake-time calculations for the scanner."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import floor

from trading_vision.data_quality import INTERVAL_LENGTHS
from trading_vision.market_calendar import ISTANBUL, BistSessionCalendar, MarketSession


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

    duration = _duration(interval)
    local_effective = effective.astimezone(ISTANBUL)
    current = calendar.session_for(local_effective.date())
    if current and local_effective >= current.opens_at + duration:
        return _latest_open_within_session(current, local_effective, duration)
    previous = calendar.latest_completed_session(now, provider_delay_seconds)
    return previous.data_closes_at - duration


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


def _latest_open_within_session(
    session: MarketSession,
    effective: datetime,
    duration: timedelta,
) -> datetime:
    if effective >= session.data_closes_at:
        return session.data_closes_at - duration
    completed = floor((effective - session.opens_at) / duration)
    return session.opens_at + duration * (completed - 1)


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
        duration = _duration(interval)
        boundary = session.opens_at + duration
        while boundary <= session.data_closes_at:
            candidate = boundary + delay
            if candidate > local_now:
                return candidate
            boundary += duration
    raise RuntimeError("Unable to calculate the next scanner wake time")


def _duration(interval: str) -> timedelta:
    return INTERVAL_LENGTHS[interval].to_pytimedelta()


def _validate_interval(interval: str) -> None:
    if interval not in INTERVAL_LENGTHS:
        raise ValueError(f"Unsupported interval: {interval}")
