"""Configuration for double-top and double-bottom detection."""

from __future__ import annotations

from dataclasses import dataclass, field

from trading_vision.patterns.pivots import PivotSettings


@dataclass(frozen=True, slots=True)
class DoublePatternSettings:
    pivot: PivotSettings = field(default_factory=PivotSettings)
    endpoint_tolerance_percent: float = 2.0
    endpoint_tolerance_atr: float = 0.75
    minimum_depth_percent: float = 2.0
    minimum_depth_atr: float = 1.0
    minimum_leg_bars: int = 3
    minimum_pattern_bars: int = 8
    maximum_pattern_bars: int = 120
    breakout_buffer_percent: float = 0.10
    breakout_buffer_atr: float = 0.10
    expiry_bars: int = 25
    invalidation_bars: int = 10
    volume_period: int = 20
    preferred_volume_ratio: float = 1.2
    lookback_bars: int = 300

    def validate(self) -> DoublePatternSettings:
        self.pivot.validate()
        positive_values = (
            self.endpoint_tolerance_percent,
            self.endpoint_tolerance_atr,
            self.minimum_depth_percent,
            self.minimum_depth_atr,
        )
        if any(value <= 0 for value in positive_values):
            raise ValueError("Double-pattern tolerances and depth limits must be positive")
        if self.minimum_leg_bars < 1 or self.minimum_pattern_bars < 2:
            raise ValueError("Double-pattern spacing must be positive")
        if self.maximum_pattern_bars <= self.minimum_pattern_bars:
            raise ValueError("Maximum pattern duration must exceed the minimum")
        if self.lookback_bars < self.maximum_pattern_bars:
            raise ValueError("Lookback must cover the maximum pattern duration")
        return self
