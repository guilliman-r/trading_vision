from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime

import pytest

from trading_vision.models import (
    AlertEvent,
    Candle,
    Drawing,
    PatternMatch,
    PatternPoint,
    Pivot,
    Symbol,
)


def test_candle_model_accepts_valid_aware_ohlcv() -> None:
    now = datetime(2026, 7, 7, 12, tzinfo=UTC)

    candle = Candle(
        interval="1d",
        opened_at_utc=now,
        open=100,
        high=105,
        low=95,
        close=102,
        volume=1_000,
        is_complete=True,
        is_adjusted=True,
        source="fixture",
        fetched_at_utc=now,
        symbol_id=1,
    )

    assert candle.close == 102
    assert candle.symbol_id == 1


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"open": 0}, "positive"),
        ({"high": 99}, "high"),
        ({"low": 103}, "low"),
        ({"volume": -1}, "volume"),
        ({"opened_at_utc": datetime(2026, 7, 7, 12)}, "opened_at_utc"),
        ({"fetched_at_utc": datetime(2026, 7, 7, 12)}, "fetched_at_utc"),
    ],
)
def test_candle_model_rejects_invalid_values(updates: dict, message: str) -> None:
    now = datetime(2026, 7, 7, 12, tzinfo=UTC)
    values = {
        "interval": "1d",
        "opened_at_utc": now,
        "open": 100,
        "high": 105,
        "low": 95,
        "close": 102,
        "volume": 1_000,
        "is_complete": True,
        "is_adjusted": True,
        "source": "fixture",
        "fetched_at_utc": now,
    }
    values.update(updates)

    with pytest.raises(ValueError, match=message):
        Candle(**values)


def test_symbol_model_is_plain_frozen_data() -> None:
    symbol = Symbol("THYAO", "THYAO.IS", is_bist=True)

    assert symbol.display_symbol == "THYAO"
    assert "provider_symbol" in {field.name for field in fields(Symbol)}
    with pytest.raises(FrozenInstanceError):
        symbol.provider_symbol = "OTHER.IS"


def test_pivot_pattern_and_alert_models_construct_without_storage_or_ui_behavior() -> None:
    now = datetime(2026, 7, 7, 12, tzinfo=UTC)
    pivot = Pivot(
        index=1,
        confirmation_index=4,
        kind="high",
        occurred_at=now,
        confirmed_at=now,
        price=105,
        atr=2,
        prominence_percent=3,
        prominence_atr=1.5,
    )
    point = PatternPoint("touch_1", pivot.index, pivot.occurred_at, pivot.price)
    pattern = PatternMatch(
        pattern_type="resistance_breakout",
        direction="bullish",
        state="forming",
        started_at=now,
        ended_at=None,
        confirmed_at=None,
        score=75,
        boundary_price=105,
        target_price=None,
        invalidation_price=99,
        points=(point,),
        reasons=("fixture reason",),
        parameters={"tolerance": 1},
        detector_version="test-v1",
    )
    alert = AlertEvent(
        id=1,
        fingerprint="fingerprint",
        pattern_id="pattern",
        provider_symbol="THYAO.IS",
        interval="1d",
        pattern_type=pattern.pattern_type,
        direction=pattern.direction,
        state="confirmed",
        score=82,
        event_at=now,
        boundary_price=pattern.boundary_price,
        target_price=None,
        app_link="/?symbol=THYAO.IS",
        created_at=now,
        acknowledged_at=None,
    )
    drawing = Drawing(
        id=1,
        symbol_id=1,
        interval="1d",
        drawing_type="line",
        shape={"type": "line"},
        created_at=now,
        updated_at=now,
    )

    for model in (pivot, point, pattern, alert, drawing):
        assert not hasattr(model, "save")
        assert not hasattr(model, "render")
        assert not hasattr(model, "connection")
