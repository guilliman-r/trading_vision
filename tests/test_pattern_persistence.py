from __future__ import annotations

from tests.test_breakouts import breakout_settings, resistance_fixture
from trading_vision.database import connect
from trading_vision.models import Symbol
from trading_vision.patterns.scoring import stable_pattern_id
from trading_vision.repositories import (
    count_pattern_transitions,
    get_pattern,
    upsert_symbol,
)
from trading_vision.services.pattern_scan import PatternScanService


def intended_resistance(matches):
    return next(
        match
        for match in matches
        if match.pattern_type == "resistance_breakout" and match.boundary_price > 99
    )


def test_rescan_deduplicates_and_records_only_real_state_changes(database_path) -> None:
    with connect(database_path) as connection:
        symbol = upsert_symbol(connection, Symbol("TEST", "TEST.IS", is_bist=True))
        scanner = PatternScanService(connection, breakout_settings())

        forming_result = scanner.scan(symbol, "1d", resistance_fixture(28, breakout=False))
        forming = intended_resistance(forming_result.matches)
        pattern_id = stable_pattern_id(symbol.provider_symbol, "1d", forming)
        assert get_pattern(connection, pattern_id)["state"] == "forming"
        assert count_pattern_transitions(connection, pattern_id) == 1

        scanner.scan(symbol, "1d", resistance_fixture(28, breakout=False))
        assert count_pattern_transitions(connection, pattern_id) == 1

        confirmed_result = scanner.scan(symbol, "1d", resistance_fixture())
        confirmed = intended_resistance(confirmed_result.matches)
        assert stable_pattern_id(symbol.provider_symbol, "1d", confirmed) == pattern_id
        assert get_pattern(connection, pattern_id)["state"] == "confirmed"
        assert count_pattern_transitions(connection, pattern_id) == 2
