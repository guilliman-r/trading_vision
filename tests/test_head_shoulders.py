from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from trading_vision.patterns.head_shoulders import detect_head_shoulders_patterns
from trading_vision.patterns.head_shoulders_settings import HeadShouldersSettings
from trading_vision.patterns.pivots import PivotSettings
from trading_vision.patterns.scoring import stable_pattern_id


def head_shoulders_settings() -> HeadShouldersSettings:
    return HeadShouldersSettings(
        pivot=PivotSettings(
            left_bars=2,
            right_bars=2,
            atr_period=3,
            minimum_prominence_atr=0.2,
            minimum_prominence_percent=0.2,
        ),
        shoulder_tolerance_percent=3.0,
        shoulder_tolerance_atr=1.0,
        minimum_head_height_percent=3.0,
        minimum_head_height_atr=0.5,
        minimum_leg_bars=3,
        minimum_pattern_bars=20,
        maximum_pattern_bars=90,
        maximum_time_imbalance=0.5,
        maximum_neckline_slope_percent_per_bar=0.5,
        expiry_bars=30,
        volume_period=10,
        lookback_bars=120,
    )


def head_shoulders_fixture(
    length: int = 65,
    head_price: float = 110.0,
    right_shoulder: float = 101.0,
    second_neckline: float = 91.0,
    confirm: bool = True,
) -> pd.DataFrame:
    if confirm:
        positions = [0, 12, 20, 30, 40, 50, 57, 58, length - 1]
        values = [82, 100, 90, head_price, second_neckline, right_shoulder, 92.5, 87, 85]
    else:
        positions = [0, 12, 20, 30, 40, 50, length - 1]
        values = [82, 100, 90, head_price, second_neckline, right_shoulder, 95]
    closes = np.interp(range(length), positions, values)
    frame = pd.DataFrame(
        {
            "opened_at_utc": pd.date_range("2025-01-01", periods=length, freq="D", tz="UTC"),
            "open": closes - 0.15,
            "high": closes + 0.8,
            "low": closes - 0.8,
            "close": closes,
            "volume": [100.0] * length,
            "is_complete": [True] * length,
        }
    )
    if confirm:
        frame.loc[58, "volume"] = 450.0
    return frame


def intended_match(frame: pd.DataFrame, pattern_type: str = "head_shoulders"):
    matches = detect_head_shoulders_patterns(frame, head_shoulders_settings())
    return next(match for match in matches if match.pattern_type == pattern_type)


def test_standard_pattern_confirms_on_first_buffered_neckline_close() -> None:
    frame = head_shoulders_fixture()
    match = intended_match(frame)
    assert match.state == "confirmed"
    assert match.confirmed_at == frame.loc[58, "opened_at_utc"].to_pydatetime()
    assert match.direction == "bearish"
    assert match.target_price < match.boundary_price
    assert match.invalidation_price > 110
    assert match.score >= 70
    assert [point.label for point in match.points] == [
        "left_shoulder",
        "neckline_low_1",
        "head",
        "neckline_low_2",
        "right_shoulder",
        "confirmation",
    ]


def test_pattern_is_forming_before_confirmation_candle() -> None:
    frame = head_shoulders_fixture()
    forming = intended_match(frame.iloc[:58])
    confirmed = intended_match(frame.iloc[:59])
    assert forming.state == "forming"
    assert forming.confirmed_at is None
    assert confirmed.state == "confirmed"
    assert confirmed.confirmed_at == frame.loc[58, "opened_at_utc"].to_pydatetime()


def test_stable_id_survives_confirmation() -> None:
    frame = head_shoulders_fixture()
    forming = intended_match(frame.iloc[:58])
    confirmed = intended_match(frame)
    assert stable_pattern_id("TEST", "1d", forming) == stable_pattern_id("TEST", "1d", confirmed)


def test_pattern_invalidates_above_head_before_confirmation() -> None:
    frame = head_shoulders_fixture(confirm=False)
    frame.loc[56, ["open", "high", "low", "close"]] = [111, 113, 110, 112]
    match = intended_match(frame)
    assert match.state == "invalidated"
    assert match.confirmed_at is None
    assert match.ended_at == frame.loc[56, "opened_at_utc"].to_pydatetime()
    assert 90 < match.boundary_price < 100


def test_confirmed_pattern_can_later_invalidate() -> None:
    frame = head_shoulders_fixture()
    frame.loc[61, ["open", "high", "low", "close"]] = [111, 113, 110, 112]
    match = intended_match(frame)
    assert match.state == "invalidated"
    assert match.confirmed_at == frame.loc[58, "opened_at_utc"].to_pydatetime()
    assert match.ended_at == frame.loc[61, "opened_at_utc"].to_pydatetime()


def test_pattern_expires_without_confirmation() -> None:
    match = intended_match(head_shoulders_fixture(length=90, confirm=False))
    assert match.state == "expired"


def test_unequal_shoulders_are_rejected() -> None:
    frame = head_shoulders_fixture(right_shoulder=115)
    matches = detect_head_shoulders_patterns(frame, head_shoulders_settings())
    assert not any(match.pattern_type == "head_shoulders" for match in matches)


def test_insufficient_head_height_is_rejected() -> None:
    frame = head_shoulders_fixture(head_price=103)
    matches = detect_head_shoulders_patterns(frame, head_shoulders_settings())
    assert not any(match.pattern_type == "head_shoulders" for match in matches)


def test_steep_neckline_is_rejected() -> None:
    frame = head_shoulders_fixture(second_neckline=100)
    settings = replace(
        head_shoulders_settings(),
        maximum_neckline_slope_percent_per_bar=0.25,
    )
    matches = detect_head_shoulders_patterns(frame, settings)
    assert not any(match.pattern_type == "head_shoulders" for match in matches)


def test_inverse_pattern_uses_mirrored_rules() -> None:
    frame = head_shoulders_fixture()
    original_open = frame["open"].copy()
    original_high = frame["high"].copy()
    original_low = frame["low"].copy()
    original_close = frame["close"].copy()
    frame["open"] = 200 - original_open
    frame["high"] = 200 - original_low
    frame["low"] = 200 - original_high
    frame["close"] = 200 - original_close
    match = intended_match(frame, "inverse_head_shoulders")
    assert match.state == "confirmed"
    assert match.direction == "bullish"
    assert match.target_price > match.boundary_price
    assert match.points[2].label == "inverse_head"


def test_detector_does_not_mutate_input() -> None:
    frame = head_shoulders_fixture()
    before = frame.copy(deep=True)
    detect_head_shoulders_patterns(frame, head_shoulders_settings())
    pd.testing.assert_frame_equal(frame, before)
