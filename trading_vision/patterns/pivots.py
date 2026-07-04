"""Confirmed local pivot extraction without future-data leakage."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from trading_vision.models import Pivot
from trading_vision.patterns.indicators import average_true_range


@dataclass(frozen=True, slots=True)
class PivotSettings:
    left_bars: int = 3
    right_bars: int = 3
    atr_period: int = 14
    minimum_prominence_atr: float = 0.5
    minimum_prominence_percent: float = 0.5

    def validate(self) -> PivotSettings:
        if self.left_bars < 1 or self.right_bars < 1:
            raise ValueError("Pivot windows must be positive")
        if self.atr_period < 2:
            raise ValueError("ATR period must be at least 2")
        if self.minimum_prominence_atr < 0 or self.minimum_prominence_percent < 0:
            raise ValueError("Pivot prominence cannot be negative")
        return self


def find_confirmed_pivots(
    candles: pd.DataFrame,
    settings: PivotSettings | None = None,
) -> list[Pivot]:
    """Find unique local extremes and record when each became knowable."""

    settings = (settings or PivotSettings()).validate()
    _validate_candles(candles)
    if len(candles) < settings.left_bars + settings.right_bars + 1:
        return []

    frame = candles.reset_index(drop=True).copy()
    atr = average_true_range(frame, settings.atr_period)
    pivots: list[Pivot] = []
    start = max(settings.left_bars, settings.atr_period - 1)
    stop = len(frame) - settings.right_bars
    for index in range(start, stop):
        high = _candidate(frame, atr, index, "high", settings)
        low = _candidate(frame, atr, index, "low", settings)
        if high:
            pivots.append(high)
        if low:
            pivots.append(low)
    pivots.sort(key=lambda pivot: (pivot.index, 0 if pivot.kind == "low" else 1))
    return _remove_adjacent_same_kind(pivots)


def _candidate(
    frame: pd.DataFrame,
    atr: pd.Series,
    index: int,
    kind: str,
    settings: PivotSettings,
) -> Pivot | None:
    left = index - settings.left_bars
    right = index + settings.right_bars
    field = "high" if kind == "high" else "low"
    window = frame.loc[left:right, field]
    price = float(frame.loc[index, field])
    extreme = float(window.max() if kind == "high" else window.min())
    if price != extreme or int((window == extreme).sum()) != 1:
        return None

    left_prices = frame.loc[left : index - 1, "low" if kind == "high" else "high"]
    right_prices = frame.loc[index + 1 : right, "low" if kind == "high" else "high"]
    prominence = _prominence(price, left_prices, right_prices, kind)
    atr_value = float(atr.iloc[index])
    if pd.isna(atr_value) or atr_value <= 0:
        return None
    prominence_percent = prominence / price * 100
    prominence_atr = prominence / atr_value
    if prominence_percent < settings.minimum_prominence_percent:
        return None
    if prominence_atr < settings.minimum_prominence_atr:
        return None

    occurred_at = pd.Timestamp(frame.loc[index, "opened_at_utc"]).to_pydatetime()
    confirmed_at = pd.Timestamp(frame.loc[right, "opened_at_utc"]).to_pydatetime()
    return Pivot(
        index=index,
        confirmation_index=right,
        kind=kind,
        occurred_at=occurred_at,
        confirmed_at=confirmed_at,
        price=price,
        atr=atr_value,
        prominence_percent=prominence_percent,
        prominence_atr=prominence_atr,
    )


def _prominence(
    price: float,
    left_prices: pd.Series,
    right_prices: pd.Series,
    kind: str,
) -> float:
    if kind == "high":
        reference = max(float(left_prices.min()), float(right_prices.min()))
        return max(0.0, price - reference)
    reference = min(float(left_prices.max()), float(right_prices.max()))
    return max(0.0, reference - price)


def _remove_adjacent_same_kind(pivots: list[Pivot]) -> list[Pivot]:
    cleaned: list[Pivot] = []
    for pivot in pivots:
        if not cleaned or cleaned[-1].kind != pivot.kind:
            cleaned.append(pivot)
            continue
        previous = cleaned[-1]
        keep_new = (
            pivot.price > previous.price if pivot.kind == "high" else pivot.price < previous.price
        )
        if keep_new:
            cleaned[-1] = pivot
    return cleaned


def _validate_candles(candles: pd.DataFrame) -> None:
    required = {"opened_at_utc", "high", "low", "close"}
    missing = required.difference(candles.columns)
    if missing:
        raise ValueError(f"Candles are missing: {', '.join(sorted(missing))}")
    if not candles["opened_at_utc"].is_monotonic_increasing:
        raise ValueError("Candles must be sorted chronologically")
