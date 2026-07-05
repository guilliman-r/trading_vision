from __future__ import annotations

from datetime import datetime

from trading_vision.freshness import STALE_GRACE, evaluate_data_freshness
from trading_vision.market_calendar import ISTANBUL, BistSessionCalendar


def test_closed_market_with_latest_daily_candle_is_current() -> None:
    freshness = evaluate_data_freshness(
        latest_candle_at=datetime(2026, 7, 3, tzinfo=ISTANBUL),
        interval="1d",
        now=datetime(2026, 7, 4, 12, tzinfo=ISTANBUL),
        is_bist=True,
        calendar=BistSessionCalendar(),
    )

    assert freshness.state == "closed"
    assert freshness.label == "Market closed · data current"
    assert freshness.market_open is False


def test_closed_market_with_missing_daily_candle_is_stale() -> None:
    freshness = evaluate_data_freshness(
        latest_candle_at=datetime(2026, 7, 2, tzinfo=ISTANBUL),
        interval="1d",
        now=datetime(2026, 7, 4, 12, tzinfo=ISTANBUL),
        is_bist=True,
        calendar=BistSessionCalendar(),
    )

    assert freshness.state == "stale"
    assert freshness.label == "Stale feed · market closed"


def test_intraday_feed_uses_interval_grace_after_market_opens() -> None:
    friday_close_bar = datetime(2026, 7, 3, 17, 55, tzinfo=ISTANBUL)
    before_grace = evaluate_data_freshness(
        latest_candle_at=friday_close_bar,
        interval="5m",
        now=datetime(2026, 7, 6, 10, 7, tzinfo=ISTANBUL),
        is_bist=True,
        provider_delay_seconds=60,
        calendar=BistSessionCalendar(),
    )
    after_grace = evaluate_data_freshness(
        latest_candle_at=friday_close_bar,
        interval="5m",
        now=datetime(2026, 7, 6, 10, 9, tzinfo=ISTANBUL),
        is_bist=True,
        provider_delay_seconds=60,
        calendar=BistSessionCalendar(),
    )

    assert STALE_GRACE["5m"].total_seconds() == 120
    assert before_grace.state == "fresh"
    assert after_grace.state == "stale"
    assert after_grace.market_open is True


def test_non_bist_feed_does_not_guess_an_exchange_schedule() -> None:
    freshness = evaluate_data_freshness(
        latest_candle_at=datetime(2026, 7, 1, tzinfo=ISTANBUL),
        interval="1d",
        now=datetime(2026, 7, 5, tzinfo=ISTANBUL),
        is_bist=False,
    )

    assert freshness.state == "unknown"
    assert freshness.label == "Exchange schedule unavailable"
    assert freshness.expected_candle_at is None
