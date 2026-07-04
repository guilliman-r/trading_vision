"""Evaluate newly created pattern transitions against explicit alert rules."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime

from trading_vision.alert_repository import (
    ensure_default_rule,
    insert_alert_event,
    is_pattern_muted,
    list_active_rules,
)
from trading_vision.data_quality import INTERVAL_LENGTHS
from trading_vision.models import PatternMatch, PatternTransition, Symbol


class AlertService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        minimum_score: float,
        enabled_pattern_types: tuple[str, ...],
    ) -> None:
        self.connection = connection
        ensure_default_rule(connection, minimum_score, enabled_pattern_types)

    def evaluate_transition(
        self,
        transition: PatternTransition,
        symbol: Symbol,
        interval: str,
        match: PatternMatch,
        latest_candle_at: datetime,
    ) -> int:
        if is_pattern_muted(self.connection, transition.pattern_id):
            return 0
        created = 0
        for rule in list_active_rules(self.connection):
            if not _matches(
                rule.required_state,
                rule.minimum_score,
                rule.pattern_types,
                transition,
                interval,
                match,
                latest_candle_at,
            ):
                continue
            fingerprint = alert_fingerprint(rule.id, transition.pattern_id, transition.new_state)
            created += int(
                insert_alert_event(
                    self.connection,
                    fingerprint,
                    rule,
                    transition,
                    symbol,
                    interval,
                    match,
                )
            )
        return created


def alert_fingerprint(rule_id: int, pattern_id: str, state: str) -> str:
    raw = f"{rule_id}:{pattern_id}:{state}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _matches(
    required_state: str,
    minimum_score: float,
    pattern_types: tuple[str, ...],
    transition: PatternTransition,
    interval: str,
    match: PatternMatch,
    latest_candle_at: datetime,
) -> bool:
    return (
        match.state == required_state
        and match.score >= minimum_score
        and match.pattern_type in pattern_types
        and _is_fresh_confirmation(transition, interval, match, latest_candle_at)
    )


def _is_fresh_confirmation(
    transition: PatternTransition,
    interval: str,
    match: PatternMatch,
    latest_candle_at: datetime,
) -> bool:
    if transition.old_state == "forming":
        return True
    if match.confirmed_at is None:
        return False
    return match.confirmed_at >= latest_candle_at - INTERVAL_LENGTHS[interval]
