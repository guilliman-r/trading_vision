"""Run pure detectors and persist their current state and transition history."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pandas as pd

from trading_vision.models import PatternMatch, Symbol
from trading_vision.pattern_repository import upsert_pattern
from trading_vision.patterns.breakouts import BreakoutSettings, detect_horizontal_breakouts
from trading_vision.patterns.double_patterns import (
    DoublePatternSettings,
    detect_double_patterns,
)
from trading_vision.patterns.head_shoulders import detect_head_shoulders_patterns
from trading_vision.patterns.head_shoulders_settings import HeadShouldersSettings
from trading_vision.patterns.scoring import stable_pattern_id
from trading_vision.patterns.triangle_settings import TriangleSettings
from trading_vision.patterns.triangles import detect_triangles
from trading_vision.services.alerts import AlertService


@dataclass(frozen=True, slots=True)
class PatternScanResult:
    matches: tuple[PatternMatch, ...]
    state_transitions: int
    alerts_created: int


class PatternScanService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        breakout_settings: BreakoutSettings | None = None,
        double_pattern_settings: DoublePatternSettings | None = None,
        head_shoulders_settings: HeadShouldersSettings | None = None,
        triangle_settings: TriangleSettings | None = None,
        minimum_alert_score: float = 70.0,
        alert_pattern_types: tuple[str, ...] = (
            "resistance_breakout",
            "support_breakdown",
        ),
    ) -> None:
        self.connection = connection
        self.breakout_settings = breakout_settings or BreakoutSettings()
        self.double_pattern_settings = double_pattern_settings or DoublePatternSettings()
        self.head_shoulders_settings = head_shoulders_settings or HeadShouldersSettings()
        self.triangle_settings = triangle_settings or TriangleSettings()
        self.minimum_alert_score = minimum_alert_score
        self.alert_pattern_types = alert_pattern_types

    def scan(
        self,
        symbol: Symbol,
        interval: str,
        candles: pd.DataFrame,
    ) -> PatternScanResult:
        if symbol.id is None:
            raise ValueError("A stored symbol is required for pattern persistence")
        matches = self.detect(candles)
        completed = candles.loc[candles["is_complete"]] if "is_complete" in candles else candles
        latest_frame = completed if not completed.empty else candles
        latest_candle_at = pd.Timestamp(latest_frame.iloc[-1]["opened_at_utc"]).to_pydatetime()
        transitions = 0
        alerts_created = 0
        alert_service = AlertService(
            self.connection,
            self.minimum_alert_score,
            self.alert_pattern_types,
        )
        for match in matches:
            pattern_id = stable_pattern_id(symbol.provider_symbol, interval, match)
            transition = upsert_pattern(self.connection, pattern_id, symbol.id, interval, match)
            if transition is None:
                continue
            transitions += 1
            alerts_created += alert_service.evaluate_transition(
                transition,
                symbol,
                interval,
                match,
                latest_candle_at,
            )
        self.connection.commit()
        return PatternScanResult(matches, transitions, alerts_created)

    def detect(self, candles: pd.DataFrame) -> tuple[PatternMatch, ...]:
        """Run enabled detectors without writing results."""

        matches = [
            *detect_horizontal_breakouts(candles, self.breakout_settings),
            *detect_double_patterns(candles, self.double_pattern_settings),
            *detect_head_shoulders_patterns(candles, self.head_shoulders_settings),
            *detect_triangles(candles, self.triangle_settings),
        ]
        return tuple(matches)
