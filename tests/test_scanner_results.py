from __future__ import annotations

from datetime import UTC, datetime

from tests.test_alerts import alert_scanner, fresh_breakout_fixture, stored_test_symbol
from trading_vision import __version__
from trading_vision.config import Settings
from trading_vision.database import connect
from trading_vision.scanner_repository import finish_scan_run, start_scan_run, update_heartbeat
from trading_vision.scanner_results import PatternResultFilters
from trading_vision.scanner_results_repository import search_pattern_results
from trading_vision.services.scanner_results import ScannerResultsService


def seed_pattern_result(database_path) -> None:
    with connect(database_path) as connection:
        symbol = stored_test_symbol(connection)
        alert_scanner(connection).scan(symbol, "1d", fresh_breakout_fixture())


def test_server_side_pattern_filters_and_bound_parameters(database_path) -> None:
    seed_pattern_result(database_path)
    with connect(database_path) as connection:
        rows = search_pattern_results(
            connection,
            PatternResultFilters(
                symbol="test",
                interval="1d",
                pattern_type="resistance_breakout",
                direction="bullish",
                state="confirmed",
                minimum_score=80,
                lookback_days=90,
            ),
        )
        assert any(row.boundary_price > 99 for row in rows)
        assert all(row.provider_symbol == "TEST.IS" for row in rows)
        assert all(row.pattern_type == "resistance_breakout" for row in rows)

        injection = search_pattern_results(
            connection,
            PatternResultFilters(symbol="' OR 1=1 --", lookback_days=0),
        )
        assert injection == []


def test_score_filter_and_csv_export_use_same_query(database_path) -> None:
    seed_pattern_result(database_path)
    filters = PatternResultFilters(
        pattern_type="resistance_breakout",
        minimum_score=80,
        lookback_days=0,
    )
    with connect(database_path) as connection:
        service = ScannerResultsService(connection, Settings(database_path=database_path))
        snapshot = service.load(filters)
        exported = service.export_csv(filters)
    assert len(snapshot.rows) >= 1
    assert "TEST.IS,1d,resistance_breakout" in exported
    assert "app_link" in exported.splitlines()[0]


def test_diagnostics_include_run_heartbeat_database_and_errors(database_path) -> None:
    moment = datetime(2026, 7, 5, 12, tzinfo=UTC)
    with connect(database_path) as connection:
        run_id = start_scan_run(connection, moment, "1d", "fixture", 2, False)
        finish_scan_run(
            connection,
            run_id,
            moment,
            succeeded=1,
            failed=1,
            candles_added=10,
            patterns_added=2,
            status="partial",
            errors=["BAD.IS: provider failed"],
            warnings=["GOOD.IS: one row quarantined"],
        )
        update_heartbeat(connection, "sleeping", 123, moment, moment, last_run_id=run_id)
        connection.commit()
        diagnostics = dict(
            ScannerResultsService(connection, Settings(database_path=database_path))
            .load(PatternResultFilters())
            .diagnostics
        )
    assert diagnostics["Scanner"] == "Sleeping"
    assert diagnostics["App version"] == f"Trading Vision {__version__}"
    assert "008_drawings.sql" in diagnostics["Schema"]
    assert "partial" in diagnostics["Last run"]
    assert diagnostics["Last success/fail"] == "1 / 1"
    assert "test.sqlite3" in diagnostics["Database"]
    assert "fixture" in diagnostics["Provider"]
    assert "dash" in diagnostics["Packages"]
    assert "BAD.IS" in diagnostics["Recent errors"]
    assert "GOOD.IS" in diagnostics["Recent warnings"]
