"""Explainable, deterministic chart-pattern detectors."""

from trading_vision.patterns.breakouts import BreakoutSettings, detect_horizontal_breakouts
from trading_vision.patterns.double_patterns import DoublePatternSettings, detect_double_patterns
from trading_vision.patterns.head_shoulders import detect_head_shoulders_patterns
from trading_vision.patterns.head_shoulders_settings import HeadShouldersSettings

__all__ = [
    "BreakoutSettings",
    "DoublePatternSettings",
    "HeadShouldersSettings",
    "detect_double_patterns",
    "detect_head_shoulders_patterns",
    "detect_horizontal_breakouts",
]
