from __future__ import annotations

from datetime import datetime

import pandas as pd

from trading_vision.candle_completion import mark_bist_candle_completion
from trading_vision.market_calendar import ISTANBUL, BistSessionCalendar


def _candles(*local_times: str) -> pd.DataFrame:
    opened_at = pd.DatetimeIndex(local_times).tz_localize(ISTANBUL).tz_convert("UTC")
    return pd.DataFrame({"opened_at_utc": opened_at, "is_complete": False})


def test_daily_candle_stays_forming_until_session_close_and_delay() -> None:
    candles = _candles("2026-07-03 00:00", "2026-07-06 00:00")

    prepared = mark_bist_candle_completion(
        candles,
        "1d",
        datetime(2026, 7, 6, 18, 15, tzinfo=ISTANBUL),
        provider_delay_seconds=600,
        calendar=BistSessionCalendar(),
    )

    assert prepared["is_complete"].tolist() == [True, False]


def test_daily_candle_completes_after_provider_delay() -> None:
    candles = _candles("2026-07-06 00:00")

    prepared = mark_bist_candle_completion(
        candles,
        "1d",
        datetime(2026, 7, 6, 18, 21, tzinfo=ISTANBUL),
        provider_delay_seconds=600,
        calendar=BistSessionCalendar(),
    )

    assert prepared["is_complete"].tolist() == [True]


def test_intraday_current_interval_waits_for_boundary_and_delay() -> None:
    candles = _candles("2026-07-06 10:00", "2026-07-06 10:15")

    before_delay = mark_bist_candle_completion(
        candles,
        "15m",
        datetime(2026, 7, 6, 10, 15, 30, tzinfo=ISTANBUL),
        provider_delay_seconds=60,
        calendar=BistSessionCalendar(),
    )
    after_delay = mark_bist_candle_completion(
        candles,
        "15m",
        datetime(2026, 7, 6, 10, 16, tzinfo=ISTANBUL),
        provider_delay_seconds=60,
        calendar=BistSessionCalendar(),
    )

    assert before_delay["is_complete"].tolist() == [False, False]
    assert after_delay["is_complete"].tolist() == [True, False]


def test_hourly_candles_use_yahoo_half_hour_boundaries() -> None:
    candles = _candles(
        "2026-07-06 09:30",
        "2026-07-06 10:30",
        "2026-07-06 11:30",
    )

    before_delay = mark_bist_candle_completion(
        candles,
        "1h",
        datetime(2026, 7, 6, 11, 30, 30, tzinfo=ISTANBUL),
        provider_delay_seconds=60,
        calendar=BistSessionCalendar(),
    )
    after_delay = mark_bist_candle_completion(
        candles,
        "1h",
        datetime(2026, 7, 6, 11, 31, tzinfo=ISTANBUL),
        provider_delay_seconds=60,
        calendar=BistSessionCalendar(),
    )

    assert before_delay["is_complete"].tolist() == [True, False, False]
    assert after_delay["is_complete"].tolist() == [True, True, False]


def test_last_hourly_candle_completes_at_exchange_data_close() -> None:
    candles = _candles("2026-07-06 17:30")

    prepared = mark_bist_candle_completion(
        candles,
        "1h",
        datetime(2026, 7, 6, 18, 1, tzinfo=ISTANBUL),
        provider_delay_seconds=60,
        calendar=BistSessionCalendar(),
    )

    assert prepared["is_complete"].tolist() == [True]


def test_weekend_uses_fridays_last_completed_interval() -> None:
    candles = _candles("2026-07-03 17:45", "2026-07-06 10:00")

    prepared = mark_bist_candle_completion(
        candles,
        "15m",
        datetime(2026, 7, 4, 12, tzinfo=ISTANBUL),
        provider_delay_seconds=60,
        calendar=BistSessionCalendar(),
    )

    assert prepared["is_complete"].tolist() == [True, False]
