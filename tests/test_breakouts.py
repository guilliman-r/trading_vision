from __future__ import annotations

import pandas as pd

from trading_vision.patterns.breakouts import BreakoutSettings, detect_horizontal_breakouts
from trading_vision.patterns.pivots import PivotSettings


def resistance_fixture(length: int = 36, breakout: bool = True) -> pd.DataFrame:
    closes = [90.0 + ((index % 5) - 2) * 0.2 for index in range(length)]
    frame = pd.DataFrame(
        {
            "opened_at_utc": pd.date_range("2025-01-01", periods=length, freq="D", tz="UTC"),
            "open": [close - 0.1 for close in closes],
            "high": [close + 1.0 for close in closes],
            "low": [close - 1.0 for close in closes],
            "close": closes,
            "volume": [100.0] * length,
            "is_complete": [True] * length,
        }
    )
    frame.loc[12, ["open", "high", "low", "close"]] = [95.0, 100.0, 94.0, 95.5]
    frame.loc[22, ["open", "high", "low", "close"]] = [95.2, 100.4, 94.2, 95.6]
    if breakout and length > 28:
        frame.loc[28:, "open"] = 102.0
        frame.loc[28:, "high"] = 104.0
        frame.loc[28:, "low"] = 101.0
        frame.loc[28:, "close"] = 103.0
        frame.loc[28, "volume"] = 500.0
    return frame


def breakout_settings() -> BreakoutSettings:
    return BreakoutSettings(
        pivot=PivotSettings(
            left_bars=2,
            right_bars=2,
            atr_period=3,
            minimum_prominence_atr=0.5,
            minimum_prominence_percent=0.5,
        ),
        minimum_touch_spacing_bars=5,
        minimum_pattern_bars=5,
        maximum_pattern_bars=60,
        expiry_bars=30,
        volume_period=10,
        lookback_bars=100,
    )


def resistance_match(frame: pd.DataFrame):
    matches = detect_horizontal_breakouts(frame, breakout_settings())
    return next(
        match
        for match in matches
        if match.pattern_type == "resistance_breakout" and match.boundary_price > 99
    )


def test_resistance_breakout_is_confirmed_on_first_buffered_close() -> None:
    match = resistance_match(resistance_fixture())
    assert match.state == "confirmed"
    assert match.confirmed_at == resistance_fixture().loc[28, "opened_at_utc"].to_pydatetime()
    assert match.boundary_price == 100.2
    assert match.target_price > match.boundary_price
    assert match.score >= 70
    assert any("confirmed touches" in reason for reason in match.reasons)


def test_same_level_is_forming_before_breakout_candle_exists() -> None:
    frame = resistance_fixture(length=28, breakout=False)
    match = resistance_match(frame)
    assert match.state == "forming"
    assert match.confirmed_at is None


def test_unbroken_level_expires_after_configured_window() -> None:
    match = resistance_match(resistance_fixture(length=60, breakout=False))
    assert match.state == "expired"
    assert match.ended_at is not None


def test_breakout_can_be_invalidated_by_return_inside_level() -> None:
    frame = resistance_fixture()
    frame.loc[31, ["open", "high", "low", "close"]] = [99.0, 99.5, 96.0, 97.0]
    match = resistance_match(frame)
    assert match.state == "invalidated"
    assert match.ended_at == frame.loc[31, "opened_at_utc"].to_pydatetime()


def test_detector_ignores_incomplete_breakout_candle() -> None:
    frame = resistance_fixture()
    frame.loc[28:, "is_complete"] = False
    match = resistance_match(frame)
    assert match.state == "forming"


def test_support_breakdown_uses_mirrored_rules_and_bearish_target() -> None:
    frame = resistance_fixture()
    original_open = frame["open"].copy()
    original_high = frame["high"].copy()
    original_low = frame["low"].copy()
    original_close = frame["close"].copy()
    frame["open"] = 200 - original_open
    frame["high"] = 200 - original_low
    frame["low"] = 200 - original_high
    frame["close"] = 200 - original_close
    matches = detect_horizontal_breakouts(frame, breakout_settings())
    match = next(
        item
        for item in matches
        if item.pattern_type == "support_breakdown" and item.boundary_price < 101
    )
    assert match.state == "confirmed"
    assert match.direction == "bearish"
    assert match.target_price < match.boundary_price


def test_nearby_highs_with_insufficient_spacing_do_not_form_level() -> None:
    frame = resistance_fixture(length=28, breakout=False)
    frame.loc[22, ["open", "high", "low", "close"]] = [90.0, 91.0, 89.0, 90.0]
    frame.loc[14, ["open", "high", "low", "close"]] = [95.0, 100.2, 94.0, 95.0]
    matches = detect_horizontal_breakouts(frame, breakout_settings())
    assert not any(
        match.pattern_type == "resistance_breakout" and match.boundary_price > 99
        for match in matches
    )
