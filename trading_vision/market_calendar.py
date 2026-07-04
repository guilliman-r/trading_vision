"""Small, data-driven Borsa Istanbul session calendar."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from trading_vision.config import PROJECT_ROOT

ISTANBUL = ZoneInfo("Europe/Istanbul")
CALENDAR_DIRECTORY = PROJECT_ROOT / "data" / "calendars"


@dataclass(frozen=True, slots=True)
class MarketSession:
    trading_date: date
    opens_at: datetime
    data_closes_at: datetime
    closes_at: datetime


class BistSessionCalendar:
    """Represent normal weekdays plus updateable holiday CSV overrides."""

    def __init__(self, directory: Path = CALENDAR_DIRECTORY) -> None:
        self.overrides = _load_overrides(directory)

    def session_for(self, trading_date: date) -> MarketSession | None:
        if trading_date.weekday() >= 5:
            return None
        override = self.overrides.get(trading_date)
        if override and override["status"] == "closed":
            return None
        data_close = time(18, 0)
        final_close = time(18, 10)
        if override and override["status"] == "half_day":
            data_close = time.fromisoformat(override["data_close"])
            final_close = time(12, 40)
        return MarketSession(
            trading_date=trading_date,
            opens_at=datetime.combine(trading_date, time(10, 0), ISTANBUL),
            data_closes_at=datetime.combine(trading_date, data_close, ISTANBUL),
            closes_at=datetime.combine(trading_date, final_close, ISTANBUL),
        )

    def is_market_open(self, now: datetime) -> bool:
        local_now = _aware_utc(now).astimezone(ISTANBUL)
        session = self.session_for(local_now.date())
        return bool(session and session.opens_at <= local_now < session.data_closes_at)

    def latest_completed_session(
        self,
        now: datetime,
        provider_delay_seconds: int = 0,
    ) -> MarketSession:
        moment = _aware_utc(now).astimezone(ISTANBUL)
        delay = timedelta(seconds=provider_delay_seconds)
        candidate = moment.date()
        for _ in range(370):
            session = self.session_for(candidate)
            if session and moment >= session.closes_at + delay:
                return session
            candidate -= timedelta(days=1)
        raise RuntimeError("No completed BIST session found within one year")

    def sessions_on_or_after(self, first_date: date):
        candidate = first_date
        while True:
            session = self.session_for(candidate)
            if session:
                yield session
            candidate += timedelta(days=1)


def _load_overrides(directory: Path) -> dict[date, dict[str, str]]:
    overrides: dict[date, dict[str, str]] = {}
    for path in sorted(directory.glob("bist_*.csv")):
        with path.open(encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                overrides[date.fromisoformat(row["date"])] = row
    return overrides


def _aware_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("Scanner timestamps must be timezone-aware")
    return moment.astimezone(UTC)
