"""BIST intraday bar times as exposed by the Yahoo Finance feed."""

from __future__ import annotations

from datetime import datetime, timedelta

from trading_vision.data_quality import INTERVAL_LENGTHS
from trading_vision.market_calendar import MarketSession

YAHOO_HOURLY_OPEN_OFFSET = timedelta(minutes=30)


def bist_intraday_opens(session: MarketSession, interval: str) -> tuple[datetime, ...]:
    """Return provider bar openings that overlap one BIST trading session.

    Yahoo labels BIST hourly bars on the half-hour: 09:30, 10:30, ...,
    17:30 Istanbul time. Shorter supported intervals start at 10:00.
    """

    duration = _duration(interval)
    current = session.opens_at
    if interval == "1h":
        current -= YAHOO_HOURLY_OPEN_OFFSET

    openings: list[datetime] = []
    while current < session.data_closes_at:
        openings.append(current)
        current += duration
    return tuple(openings)


def bist_intraday_close(
    opened_at: datetime,
    session: MarketSession,
    interval: str,
) -> datetime:
    """Return the completion boundary for a provider bar.

    The last hourly bar can be shorter than one hour because it ends at the
    exchange data close.
    """

    return min(opened_at + _duration(interval), session.data_closes_at)


def latest_completed_intraday_open(
    session: MarketSession,
    interval: str,
    effective_time: datetime,
) -> datetime | None:
    """Return the latest bar whose full provider boundary has passed."""

    latest = None
    for opened_at in bist_intraday_opens(session, interval):
        if bist_intraday_close(opened_at, session, interval) > effective_time:
            break
        latest = opened_at
    return latest


def _duration(interval: str) -> timedelta:
    if interval == "1d" or interval not in INTERVAL_LENGTHS:
        raise ValueError(f"Unsupported intraday interval: {interval}")
    return INTERVAL_LENGTHS[interval].to_pytimedelta()
