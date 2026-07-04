from __future__ import annotations

import sqlite3

import pytest

from tests.test_breakouts import breakout_settings, resistance_fixture
from trading_vision.alert_repository import (
    acknowledge_alert,
    acknowledge_all_alerts,
    is_pattern_muted,
    list_recent_alerts,
    mute_alert_pattern,
    mute_pattern,
    unread_alert_count,
)
from trading_vision.database import connect, connection_scope
from trading_vision.models import Symbol
from trading_vision.patterns.scoring import stable_pattern_id
from trading_vision.repositories import upsert_symbol
from trading_vision.services.alerts import AlertService, alert_fingerprint
from trading_vision.services.pattern_scan import PatternScanService


def alert_scanner(connection, minimum_score: float = 70) -> PatternScanService:
    return PatternScanService(
        connection,
        breakout_settings=breakout_settings(),
        minimum_alert_score=minimum_score,
        alert_pattern_types=("resistance_breakout", "support_breakdown"),
    )


def stored_test_symbol(connection) -> Symbol:
    return upsert_symbol(connection, Symbol("TEST", "TEST.IS", is_bist=True))


def intended_resistance(matches):
    return next(
        match
        for match in matches
        if match.pattern_type == "resistance_breakout" and match.boundary_price > 99
    )


def fresh_breakout_fixture():
    return resistance_fixture(length=29)


def test_alert_is_created_only_for_new_confirmed_transition(database_path) -> None:
    with connect(database_path) as connection:
        symbol = stored_test_symbol(connection)
        scanner = alert_scanner(connection)
        forming = scanner.scan(symbol, "1d", resistance_fixture(28, breakout=False))
        assert forming.alerts_created == 0
        assert unread_alert_count(connection) == 0

        confirmed = scanner.scan(symbol, "1d", fresh_breakout_fixture())
        assert confirmed.alerts_created == 1
        assert unread_alert_count(connection) == 1
        event = list_recent_alerts(connection)[0]
        assert event.provider_symbol == "TEST.IS"
        assert event.pattern_type == "resistance_breakout"
        assert event.state == "confirmed"
        assert event.score >= 70
        assert event.boundary_price > 99
        assert event.target_price is not None
        assert "symbol=TEST.IS" in event.app_link


def test_duplicate_restart_score_change_and_invalidation_do_not_realert(database_path) -> None:
    with connect(database_path) as connection:
        symbol = stored_test_symbol(connection)
        scanner = alert_scanner(connection)
        scanner.scan(symbol, "1d", fresh_breakout_fixture())

        changed_volume = fresh_breakout_fixture()
        changed_volume.loc[28, "volume"] = 900
        restarted_scanner = alert_scanner(connection)
        assert restarted_scanner.scan(symbol, "1d", changed_volume).alerts_created == 0

        invalidated = resistance_fixture()
        invalidated.loc[31, ["open", "high", "low", "close"]] = [99, 99.5, 96, 97]
        assert restarted_scanner.scan(symbol, "1d", invalidated).alerts_created == 0
        assert len(list_recent_alerts(connection)) == 1


def test_score_threshold_and_pattern_mute_suppress_alert(database_path) -> None:
    with connect(database_path) as connection:
        symbol = stored_test_symbol(connection)
        high_threshold = alert_scanner(connection, minimum_score=100)
        assert high_threshold.scan(symbol, "1d", fresh_breakout_fixture()).alerts_created == 0

    other_database = database_path.with_name("muted.sqlite3")
    from trading_vision.database import initialize_database

    initialize_database(other_database)
    with connect(other_database) as connection:
        symbol = stored_test_symbol(connection)
        scanner = alert_scanner(connection)
        forming_result = scanner.scan(symbol, "1d", resistance_fixture(28, breakout=False))
        match = intended_resistance(forming_result.matches)
        pattern_id = stable_pattern_id(symbol.provider_symbol, "1d", match)
        mute_pattern(connection, pattern_id, "test mute")
        connection.commit()
        assert scanner.scan(symbol, "1d", fresh_breakout_fixture()).alerts_created == 0
        assert unread_alert_count(connection) == 0


def test_acknowledge_all_and_mute_actions_are_idempotent(database_path) -> None:
    with connect(database_path) as connection:
        symbol = stored_test_symbol(connection)
        alert_scanner(connection).scan(symbol, "1d", fresh_breakout_fixture())
        event = list_recent_alerts(connection)[0]

        acknowledge_alert(connection, event.id)
        acknowledge_alert(connection, event.id)
        assert unread_alert_count(connection) == 0

        mute_alert_pattern(connection, event.id)
        mute_alert_pattern(connection, event.id)
        assert is_pattern_muted(connection, event.pattern_id)

        acknowledge_all_alerts(connection)
        assert unread_alert_count(connection) == 0


def test_alert_and_transition_roll_back_together(database_path, monkeypatch) -> None:
    def fail_evaluation(*_arguments, **_keywords):
        raise RuntimeError("deliberate alert failure")

    monkeypatch.setattr(AlertService, "evaluate_transition", fail_evaluation)
    with (
        pytest.raises(RuntimeError, match="deliberate alert failure"),
        connection_scope(database_path) as connection,
    ):
        symbol = stored_test_symbol(connection)
        alert_scanner(connection).scan(symbol, "1d", fresh_breakout_fixture())

    with connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM patterns").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM pattern_transitions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM alert_events").fetchone()[0] == 0


def test_alert_fingerprint_is_stable_and_rule_specific() -> None:
    first = alert_fingerprint(1, "pattern-1", "confirmed")
    assert first == alert_fingerprint(1, "pattern-1", "confirmed")
    assert first != alert_fingerprint(2, "pattern-1", "confirmed")
    assert len(first) == 32


def test_database_enforces_unique_alert_fingerprint(database_path) -> None:
    with connect(database_path) as connection:
        symbol = stored_test_symbol(connection)
        alert_scanner(connection).scan(symbol, "1d", fresh_breakout_fixture())
        event = connection.execute("SELECT * FROM alert_events").fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO alert_events (
                    fingerprint, rule_id, transition_id, pattern_id, symbol_id,
                    provider_symbol, interval, pattern_type, direction, state,
                    score, event_at_utc, boundary_price, target_price, app_link,
                    created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(
                    event[key]
                    for key in (
                        "fingerprint",
                        "rule_id",
                        "transition_id",
                        "pattern_id",
                        "symbol_id",
                        "provider_symbol",
                        "interval",
                        "pattern_type",
                        "direction",
                        "state",
                        "score",
                        "event_at_utc",
                        "boundary_price",
                        "target_price",
                        "app_link",
                        "created_at_utc",
                    )
                ),
            )


def test_old_confirmation_discovered_on_first_scan_does_not_alert(database_path) -> None:
    with connect(database_path) as connection:
        symbol = stored_test_symbol(connection)
        result = alert_scanner(connection).scan(symbol, "1d", resistance_fixture())
        assert result.alerts_created == 0
        assert unread_alert_count(connection) == 0


def test_forming_pattern_can_alert_after_offline_catch_up(database_path) -> None:
    with connect(database_path) as connection:
        symbol = stored_test_symbol(connection)
        scanner = alert_scanner(connection)
        scanner.scan(symbol, "1d", resistance_fixture(28, breakout=False))
        result = scanner.scan(symbol, "1d", resistance_fixture())
        assert result.alerts_created == 1


def test_inactive_rule_does_not_create_alert(database_path) -> None:
    with connect(database_path) as connection:
        symbol = stored_test_symbol(connection)
        scanner = alert_scanner(connection)
        scanner.scan(symbol, "1d", resistance_fixture(28, breakout=False))
        connection.execute("UPDATE alert_rules SET is_active = 0")
        connection.commit()
        result = scanner.scan(symbol, "1d", fresh_breakout_fixture())
        assert result.alerts_created == 0
        assert unread_alert_count(connection) == 0
