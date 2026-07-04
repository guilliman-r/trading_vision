from __future__ import annotations

from tests.test_breakouts import breakout_settings, resistance_fixture
from tests.test_double_patterns import double_settings, double_top_fixture
from tests.test_head_shoulders import head_shoulders_fixture, head_shoulders_settings
from tests.test_triangles import ascending_triangle_fixture, triangle_settings
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


def test_double_top_keeps_identity_across_forming_and_confirmed_states(database_path) -> None:
    with connect(database_path) as connection:
        symbol = upsert_symbol(connection, Symbol("TEST", "TEST.IS", is_bist=True))
        scanner = PatternScanService(
            connection,
            breakout_settings=breakout_settings(),
            double_pattern_settings=double_settings(),
        )
        forming_result = scanner.scan(symbol, "1d", double_top_fixture().iloc[:34])
        forming = next(
            match for match in forming_result.matches if match.pattern_type == "double_top"
        )
        pattern_id = stable_pattern_id(symbol.provider_symbol, "1d", forming)
        assert get_pattern(connection, pattern_id)["state"] == "forming"

        confirmed_result = scanner.scan(symbol, "1d", double_top_fixture())
        confirmed = next(
            match for match in confirmed_result.matches if match.pattern_type == "double_top"
        )
        assert stable_pattern_id(symbol.provider_symbol, "1d", confirmed) == pattern_id
        assert get_pattern(connection, pattern_id)["state"] == "confirmed"
        assert count_pattern_transitions(connection, pattern_id) == 2


def test_head_shoulders_keeps_identity_across_state_transition(database_path) -> None:
    with connect(database_path) as connection:
        symbol = upsert_symbol(connection, Symbol("TEST", "TEST.IS", is_bist=True))
        scanner = PatternScanService(
            connection,
            breakout_settings=breakout_settings(),
            double_pattern_settings=double_settings(),
            head_shoulders_settings=head_shoulders_settings(),
        )
        forming_result = scanner.scan(symbol, "1d", head_shoulders_fixture().iloc[:58])
        forming = next(
            match for match in forming_result.matches if match.pattern_type == "head_shoulders"
        )
        pattern_id = stable_pattern_id(symbol.provider_symbol, "1d", forming)
        assert get_pattern(connection, pattern_id)["state"] == "forming"

        confirmed_result = scanner.scan(symbol, "1d", head_shoulders_fixture())
        confirmed = next(
            match for match in confirmed_result.matches if match.pattern_type == "head_shoulders"
        )
        assert stable_pattern_id(symbol.provider_symbol, "1d", confirmed) == pattern_id
        assert get_pattern(connection, pattern_id)["state"] == "confirmed"
        assert count_pattern_transitions(connection, pattern_id) == 2


def test_triangle_keeps_identity_across_state_transition(database_path) -> None:
    with connect(database_path) as connection:
        symbol = upsert_symbol(connection, Symbol("TEST", "TEST.IS", is_bist=True))
        scanner = PatternScanService(
            connection,
            breakout_settings=breakout_settings(),
            double_pattern_settings=double_settings(),
            head_shoulders_settings=head_shoulders_settings(),
            triangle_settings=triangle_settings(),
        )
        forming_result = scanner.scan(symbol, "1d", ascending_triangle_fixture().iloc[:42])
        forming = next(
            match for match in forming_result.matches if match.pattern_type == "ascending_triangle"
        )
        pattern_id = stable_pattern_id(symbol.provider_symbol, "1d", forming)
        assert get_pattern(connection, pattern_id)["state"] == "forming"

        confirmed_result = scanner.scan(symbol, "1d", ascending_triangle_fixture())
        confirmed = next(
            match
            for match in confirmed_result.matches
            if match.pattern_type == "ascending_triangle"
        )
        assert stable_pattern_id(symbol.provider_symbol, "1d", confirmed) == pattern_id
        assert get_pattern(connection, pattern_id)["state"] == "confirmed"
        assert count_pattern_transitions(connection, pattern_id) == 2
