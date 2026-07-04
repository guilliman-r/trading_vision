from trading_vision.database import MIGRATIONS_DIRECTORY, connect, initialize_database
from trading_vision.models import Symbol
from trading_vision.repositories import find_symbol, upsert_symbol


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
