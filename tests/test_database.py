import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from trading_vision.data_quality import prepare_candles
from trading_vision.database import (
    MIGRATIONS_DIRECTORY,
    connect,
    connection_scope,
    initialize_database,
    schema_version,
)
from trading_vision.models import Symbol
from trading_vision.repositories import (
    find_symbol,
    get_candles_between,
    get_latest_candle,
    list_active_symbols,
    mark_symbol_inactive,
    search_symbols,
    upsert_candles,
    upsert_symbol,
)

FIXTURES_DIRECTORY = Path(__file__).parent / "fixtures"


def test_migrations_are_idempotent(database_path) -> None:
    initialize_database(database_path)
    with connect(database_path) as connection:
        migrations = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert migrations == len(list(MIGRATIONS_DIRECTORY.glob("*.sql")))


def test_schema_version_reports_latest_applied_migration(database_path) -> None:
    with connect(database_path) as connection:
        version = schema_version(connection)

    assert "006_watchlists_settings.sql" in version
    assert f"{len(list(MIGRATIONS_DIRECTORY.glob('*.sql')))} migrations" in version


def test_database_upgrades_from_committed_schema_fixture(tmp_path: Path) -> None:
    database_path = tmp_path / "schema_005.sqlite3"
    fixture = FIXTURES_DIRECTORY / "schema_005.sql"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(fixture.read_text(encoding="utf-8"))

    initialize_database(database_path)

    with connect(database_path) as connection:
        migrations = [
            row["filename"]
            for row in connection.execute(
                "SELECT filename FROM schema_migrations ORDER BY filename"
            )
        ]
        watchlists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'watchlists'"
        ).fetchone()
        app_settings = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'app_settings'"
        ).fetchone()

    assert migrations == sorted(path.name for path in MIGRATIONS_DIRECTORY.glob("*.sql"))
    assert watchlists is not None
    assert app_settings is not None


def test_symbol_can_be_inserted_and_found(database_path) -> None:
    with connect(database_path) as connection:
        stored = upsert_symbol(
            connection,
            Symbol("THYAO", "THYAO.IS", "Türk Hava Yolları", "XIST", "TRY", True),
        )
        found = find_symbol(connection, "thyao")
    assert stored.id is not None
    assert found == stored


def test_bist_display_symbol_wins_over_prior_generic_symbol(database_path) -> None:
    with connect(database_path) as connection:
        upsert_symbol(connection, Symbol("GARAN", "GARAN", is_bist=False))
        bist = upsert_symbol(connection, Symbol("GARAN", "GARAN.IS", is_bist=True))
        found = find_symbol(connection, "GARAN")
    assert found == bist


def test_symbol_search_matches_ticker_provider_symbol_and_company_name(database_path) -> None:
    with connect(database_path) as connection:
        thyao = upsert_symbol(
            connection,
            Symbol("THYAO", "THYAO.IS", "Türk Hava Yolları", "XIST", "TRY", True),
        )
        upsert_symbol(
            connection,
            Symbol("OLD", "OLD.IS", "Inactive Company", "XIST", "TRY", True, False),
        )

        ticker_matches = search_symbols(connection, "THYAO")
        provider_matches = search_symbols(connection, "THYAO.IS")
        company_matches = search_symbols(connection, "Hava Yolları")
        ascii_company_matches = search_symbols(connection, "Turk Hava Yollari")
        inactive_matches = search_symbols(connection, "Inactive")

    assert ticker_matches == [thyao]
    assert provider_matches == [thyao]
    assert company_matches == [thyao]
    assert ascii_company_matches == [thyao]
    assert inactive_matches == []


def test_active_symbol_listing_and_inactive_marker(database_path) -> None:
    with connect(database_path) as connection:
        thyao = upsert_symbol(connection, Symbol("THYAO", "THYAO.IS", is_bist=True))
        aapl = upsert_symbol(connection, Symbol("AAPL", "AAPL", is_bist=False))
        upsert_symbol(connection, Symbol("OLD", "OLD.IS", is_bist=True, is_active=False))

        assert list_active_symbols(connection) == [thyao, aapl]
        assert list_active_symbols(connection, is_bist=True) == [thyao]
        assert list_active_symbols(connection, is_bist=False) == [aapl]
        assert mark_symbol_inactive(connection, "thyao.is")
        assert not mark_symbol_inactive(connection, "missing")

        remaining = list_active_symbols(connection)

    assert remaining == [aapl]


def test_candle_range_and_latest_queries(database_path) -> None:
    with connect(database_path) as connection:
        symbol = upsert_symbol(connection, Symbol("TEST", "TEST.IS", is_bist=True))
        frame = pd.DataFrame(
            {
                "open": [10.0, 11.0, 12.0],
                "high": [12.0, 13.0, 14.0],
                "low": [9.0, 10.0, 11.0],
                "close": [11.0, 12.0, 13.0],
                "volume": [100.0, 150.0, 200.0],
            },
            index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"], utc=True),
        )
        candles = prepare_candles(frame, "1d", "fixture")
        upsert_candles(connection, symbol.id, "1d", candles)

        ranged = get_candles_between(
            connection,
            symbol.id,
            "1d",
            datetime(2026, 1, 2, tzinfo=UTC),
            datetime(2026, 1, 3, tzinfo=UTC),
        )
        latest = get_latest_candle(connection, symbol.id, "1d")

    assert ranged["close"].tolist() == [12.0, 13.0]
    assert ranged["is_complete"].tolist() == [True, True]
    assert latest is not None
    assert latest["opened_at_utc"] == pd.Timestamp("2026-01-03", tz="UTC")
    assert latest["close"] == 13.0


def test_connection_scope_commits_and_closes(database_path) -> None:
    with connection_scope(database_path) as connection:
        upsert_symbol(connection, Symbol("TEST", "TEST"))

    with connect(database_path) as verification_connection:
        assert find_symbol(verification_connection, "TEST") is not None

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")
