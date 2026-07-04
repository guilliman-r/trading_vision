"""Configuration for standard and inverse head-and-shoulders patterns."""

from __future__ import annotations

from dataclasses import dataclass, field

from trading_vision.patterns.pivots import PivotSettings


@dataclass(frozen=True, slots=True)
class HeadShouldersSettings:
    pivot: PivotSettings = field(default_factory=PivotSettings)
    shoulder_tolerance_percent: float = 3.0
    shoulder_tolerance_atr: float = 1.0
    minimum_head_height_percent: float = 3.0
    minimum_head_height_atr: float = 1.0
    minimum_leg_bars: int = 2
    minimum_pattern_bars: int = 12
    maximum_pattern_bars: int = 160
    maximum_time_imbalance: float = 0.60
    maximum_neckline_slope_percent_per_bar: float = 0.50
    breakout_buffer_percent: float = 0.10
    breakout_buffer_atr: float = 0.10
    expiry_bars: int = 30
    invalidation_bars: int = 10
    volume_period: int = 20
    preferred_volume_ratio: float = 1.2
    lookback_bars: int = 350

    def validate(self) -> HeadShouldersSettings:
        self.pivot.validate()
        if self.shoulder_tolerance_percent <= 0 or self.shoulder_tolerance_atr <= 0:
            raise ValueError("Shoulder tolerances must be positive")
        if self.minimum_head_height_percent <= 0 or self.minimum_head_height_atr <= 0:
            raise ValueError("Head prominence limits must be positive")
        if self.minimum_leg_bars < 1 or self.minimum_pattern_bars < 4:
            raise ValueError("Pattern spacing must be positive")
        if self.maximum_pattern_bars <= self.minimum_pattern_bars:
            raise ValueError("Maximum duration must exceed minimum duration")
        if not 0 <= self.maximum_time_imbalance < 1:
            raise ValueError("Time imbalance must be between 0 and 1")
        if self.maximum_neckline_slope_percent_per_bar <= 0:
            raise ValueError("Neckline slope limit must be positive")
        if self.lookback_bars < self.maximum_pattern_bars:
            raise ValueError("Lookback must cover maximum pattern duration")
        return self
