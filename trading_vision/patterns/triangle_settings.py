"""Configuration for ascending, descending, and symmetrical triangles."""

from __future__ import annotations

from dataclasses import dataclass, field

from trading_vision.patterns.pivots import PivotSettings


@dataclass(frozen=True, slots=True)
class TriangleSettings:
    pivot: PivotSettings = field(default_factory=PivotSettings)
    minimum_touches_per_side: int = 2
    minimum_pattern_bars: int = 8
    maximum_pattern_bars: int = 120
    flat_slope_percent_per_bar: float = 0.08
    minimum_trend_slope_percent_per_bar: float = 0.03
    minimum_convergence_percent: float = 10.0
    minimum_apex_distance_bars: int = 2
    maximum_apex_distance_bars: int = 120
    breakout_buffer_percent: float = 0.10
    breakout_buffer_atr: float = 0.10
    expiry_bars: int = 30
    invalidation_bars: int = 8
    volume_period: int = 20
    preferred_volume_ratio: float = 1.2
    lookback_bars: int = 350

    def validate(self) -> TriangleSettings:
        self.pivot.validate()
        if self.minimum_touches_per_side < 2:
            raise ValueError("Triangles require at least two touches per side")
        if self.minimum_pattern_bars < 3 or self.maximum_pattern_bars <= self.minimum_pattern_bars:
            raise ValueError("Triangle duration limits are invalid")
        if self.flat_slope_percent_per_bar <= 0:
            raise ValueError("Flat-line slope tolerance must be positive")
        if self.minimum_trend_slope_percent_per_bar <= 0:
            raise ValueError("Trend-line slope minimum must be positive")
        if not 0 < self.minimum_convergence_percent < 100:
            raise ValueError("Convergence must be between 0 and 100 percent")
        if self.minimum_apex_distance_bars < 1:
            raise ValueError("Apex distance must be positive")
        if self.maximum_apex_distance_bars <= self.minimum_apex_distance_bars:
            raise ValueError("Maximum apex distance must exceed the minimum")
        if self.lookback_bars < self.maximum_pattern_bars:
            raise ValueError("Lookback must cover maximum pattern duration")
        return self
