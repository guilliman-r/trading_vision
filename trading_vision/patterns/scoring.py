"""Stable IDs and small scoring helpers."""

from __future__ import annotations

import hashlib

from trading_vision.models import PatternMatch


def stable_pattern_id(symbol: str, interval: str, match: PatternMatch) -> str:
    """Create an ID that remains stable as a forming pattern gains more touches."""

    defining_points = match.points[:2]
    timestamps = ":".join(point.occurred_at.isoformat() for point in defining_points)
    raw = f"{symbol}:{interval}:{match.pattern_type}:{timestamps}:{match.detector_version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)
