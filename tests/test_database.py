import sqlite3

import pytest

from trading_vision.database import (
    MIGRATIONS_DIRECTORY,
    connect,
    connection_scope,
    initialize_database,
)
from trading_vision.models import Symbol
from trading_vision.repositories import find_symbol, search_symbols, upsert_symbol


def test_migrations_are_idempotent(database_path) -> None:
    initialize_database(database_path)
    with connect(database_path) as connection:
        migrations = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert migrations == len(list(MIGRATIONS_DIRECTORY.glob("*.sql")))


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


def test_connection_scope_commits_and_closes(database_path) -> None:
    with connection_scope(database_path) as connection:
        upsert_symbol(connection, Symbol("TEST", "TEST"))

    with connect(database_path) as verification_connection:
        assert find_symbol(verification_connection, "TEST") is not None

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")
