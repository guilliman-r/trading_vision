from __future__ import annotations

from datetime import UTC, datetime, timedelta

from trading_vision.pattern_focus import pattern_focus_range


def test_daily_pattern_focus_range_pads_both_sides() -> None:
    started = datetime(2026, 7, 1, tzinfo=UTC)
    confirmed = datetime(2026, 7, 8, tzinfo=UTC)
    last_seen = datetime(2026, 7, 9, tzinfo=UTC)

    range_from, range_to = pattern_focus_range("1d", started, confirmed, last_seen)

    assert range_from == started - timedelta(days=5)
    assert range_to == confirmed + timedelta(days=5)


def test_hourly_forming_pattern_focus_uses_last_seen_time() -> None:
    started = datetime(2026, 7, 8, 9, 30, tzinfo=UTC)
    last_seen = datetime(2026, 7, 8, 14, 30, tzinfo=UTC)

    range_from, range_to = pattern_focus_range("1h", started, None, last_seen)

    assert range_from == started - timedelta(hours=6)
    assert range_to == last_seen + timedelta(hours=6)
