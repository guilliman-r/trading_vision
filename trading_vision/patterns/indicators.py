"""Small financial calculations shared by pattern detectors."""

from __future__ import annotations

import numpy as np
import pandas as pd


def true_range(candles: pd.DataFrame) -> pd.Series:
    """Return the greatest intrabar or previous-close range for each candle."""

    previous_close = candles["close"].shift(1)
    ranges = pd.concat(
        [
            candles["high"] - candles["low"],
            (candles["high"] - previous_close).abs(),
            (candles["low"] - previous_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def average_true_range(candles: pd.DataFrame, period: int = 14) -> pd.Series:
    """Return a simple rolling average of true range."""

    if period < 1:
        raise ValueError("ATR period must be positive")
    return true_range(candles).rolling(period, min_periods=period).mean()


def percent_distance(first: float, second: float) -> float:
    """Return absolute distance as a percentage of the pair's midpoint."""

    midpoint = (abs(first) + abs(second)) / 2
    return 0.0 if midpoint == 0 else abs(first - second) / midpoint * 100


def rolling_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Compare volume with the preceding rolling median, excluding the current bar."""

    baseline = volume.shift(1).rolling(period, min_periods=max(3, period // 2)).median()
    baseline = baseline.replace(0, np.nan)
    return volume / baseline


def fit_line(indices: list[int], prices: list[float]) -> tuple[float, float]:
    """Fit `price = slope * candle_index + intercept` using least squares."""

    if len(indices) != len(prices) or len(indices) < 2:
        raise ValueError("Line fitting requires at least two paired points")
    slope, intercept = np.polyfit(indices, prices, 1)
    return float(slope), float(intercept)


def line_value(slope: float, intercept: float, candle_index: int) -> float:
    return slope * candle_index + intercept


def crossed_boundary(
    close: float,
    boundary: float,
    buffer: float,
    direction: str,
) -> bool:
    if direction == "above":
        return close > boundary + buffer
    if direction == "below":
        return close < boundary - buffer
    raise ValueError("direction must be 'above' or 'below'")
