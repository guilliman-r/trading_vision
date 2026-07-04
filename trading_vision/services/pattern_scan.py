"""Run pure detectors and persist their current state and transition history."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pandas as pd

from trading_vision.models import PatternMatch, Symbol
from trading_vision.patterns.breakouts import BreakoutSettings, detect_horizontal_breakouts
from trading_vision.patterns.double_patterns import (
    DoublePatternSettings,
    detect_double_patterns,
)
from trading_vision.patterns.scoring import stable_pattern_id
from trading_vision.repositories import upsert_pattern


@dataclass(frozen=True, slots=True)
class PatternScanResult:
    matches: tuple[PatternMatch, ...]
    state_transitions: int


class PatternScanService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        breakout_settings: BreakoutSettings | None = None,
        double_pattern_settings: DoublePatternSettings | None = None,
    ) -> None:
        self.connection = connection
        self.breakout_settings = breakout_settings or BreakoutSettings()
        self.double_pattern_settings = double_pattern_settings or DoublePatternSettings()

    def scan(
        self,
        symbol: Symbol,
        interval: str,
        candles: pd.DataFrame,
    ) -> PatternScanResult:
        if symbol.id is None:
            raise ValueError("A stored symbol is required for pattern persistence")
        matches = [
            *detect_horizontal_breakouts(candles, self.breakout_settings),
            *detect_double_patterns(candles, self.double_pattern_settings),
        ]
        transitions = 0
        for match in matches:
            pattern_id = stable_pattern_id(symbol.provider_symbol, interval, match)
            transitions += int(
                upsert_pattern(self.connection, pattern_id, symbol.id, interval, match)
            )
        self.connection.commit()
        return PatternScanResult(tuple(matches), transitions)
