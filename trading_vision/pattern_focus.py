"""Shared time windows for opening a chart around a pattern."""

from __future__ import annotations

from datetime import datetime, timedelta


def pattern_focus_range(
    interval: str,
    started_at: datetime,
    confirmed_at: datetime | None,
    last_seen_at: datetime,
) -> tuple[datetime, datetime]:
    padding = _range_padding(interval)
    end = confirmed_at or last_seen_at
    return started_at - padding, end + padding


def _range_padding(interval: str) -> timedelta:
    if interval == "1d":
        return timedelta(days=5)
    if interval == "1h":
        return timedelta(hours=6)
    if interval == "15m":
        return timedelta(hours=2)
    if interval == "5m":
        return timedelta(hours=1)
    return timedelta(days=5)
