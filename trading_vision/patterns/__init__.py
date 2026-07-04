"""Explainable, deterministic chart-pattern detectors."""

from trading_vision.patterns.breakouts import BreakoutSettings, detect_horizontal_breakouts
from trading_vision.patterns.double_patterns import DoublePatternSettings, detect_double_patterns

__all__ = [
    "BreakoutSettings",
    "DoublePatternSettings",
    "detect_double_patterns",
    "detect_horizontal_breakouts",
]
