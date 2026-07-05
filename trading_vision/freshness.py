"""Explain whether the latest BIST candle is current for the market state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from trading_vision.data_quality import INTERVAL_LENGTHS
from trading_vision.market_calendar import ISTANBUL, BistSessionCalendar
from trading_vision.scanner_schedule import expected_latest_open

STALE_GRACE = {
    "5m": timedelta(minutes=2),
    "15m": timedelta(minutes=3),
    "1h": timedelta(minutes=5),
    "1d": timedelta(minutes=15),
}


@dataclass(frozen=True, slots=True)
class DataFreshness:
    state: str
    label: str
    expected_candle_at: datetime | None
    market_open: bool | None


def evaluate_data_freshness(
    latest_candle_at: datetime,
    interval: str,
    now: datetime,
    is_bist: bool,
    provider_delay_seconds: int = 60,
    calendar: BistSessionCalendar | None = None,
) -> DataFreshness:
    """Compare the latest candle with the most recent eligible BIST candle."""

    if interval not in INTERVAL_LENGTHS:
        raise ValueError(f"Unsupported interval: {interval}")
    _require_aware(latest_candle_at, "Latest candle")
    _require_aware(now, "Current time")
    if not is_bist:
        return DataFreshness("unknown", "Exchange schedule unavailable", None, None)

    session_calendar = calendar or BistSessionCalendar()
    delay = provider_delay_seconds + int(STALE_GRACE[interval].total_seconds())
    expected = expected_latest_open(interval, now, delay, session_calendar)
    market_open = session_calendar.is_market_open(now)
    stale = _is_older_than_expected(latest_candle_at, expected, interval)
    market_label = "market open" if market_open else "market closed"
    if stale:
        return DataFreshness("stale", f"Stale feed · {market_label}", expected, market_open)
    if market_open:
        return DataFreshness("fresh", "Market open · data current", expected, True)
    return DataFreshness("closed", "Market closed · data current", expected, False)


def _is_older_than_expected(latest: datetime, expected: datetime, interval: str) -> bool:
    if interval == "1d":
        return latest.astimezone(ISTANBUL).date() < expected.astimezone(ISTANBUL).date()
    return latest.astimezone(UTC) < expected.astimezone(UTC)


def _require_aware(moment: datetime, label: str) -> None:
    if moment.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
