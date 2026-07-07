from datetime import UTC, datetime

from trading_vision.config import Settings
from trading_vision.database import connect
from trading_vision.models import Symbol
from trading_vision.providers.base import MarketDataProvider
from trading_vision.repositories import find_symbol, upsert_symbol
from trading_vision.scanner_repository import update_heartbeat
from trading_vision.ui.app import create_app


class OfflineProvider(MarketDataProvider):
    pass


def test_app_factory_builds_layout(database_path) -> None:
    settings = Settings(database_path=database_path)
    app = create_app(settings=settings, provider=OfflineProvider())
    assert app.title == "Trading Vision"
    assert app.layout.id == "app-root"


def test_app_startup_initializes_database_and_imports_catalog(tmp_path) -> None:
    database_path = tmp_path / "fresh" / "startup.sqlite3"

    create_app(settings=Settings(database_path=database_path), provider=OfflineProvider())

    with connect(database_path) as connection:
        migration_count = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        thyao = find_symbol(connection, "THYAO")

    assert migration_count > 0
    assert thyao is not None
    assert thyao.provider_symbol == "THYAO.IS"


def test_layout_displays_persisted_scanner_heartbeat(database_path) -> None:
    moment = datetime(2026, 7, 4, 12, tzinfo=UTC)
    with connect(database_path) as connection:
        update_heartbeat(connection, "sleeping", 123, moment, moment)
        connection.commit()
    app = create_app(Settings(database_path=database_path), OfflineProvider())
    client = app.server.test_client()
    layout = client.get("/_dash-layout")
    assert b"Scanner Sleeping" in layout.data


def test_layout_populates_symbol_suggestions_from_database(database_path) -> None:
    with connect(database_path) as connection:
        upsert_symbol(
            connection,
            Symbol(
                "TESTX",
                "TESTX.IS",
                "Test Exchange Company",
                "XIST",
                "TRY",
                True,
            ),
        )
        connection.commit()

    app = create_app(Settings(database_path=database_path), OfflineProvider())
    client = app.server.test_client()
    layout = client.get("/_dash-layout")

    assert b'"symbol-suggestions"' in layout.data
    assert b'"TESTX"' in layout.data
    assert b"Test Exchange Company" in layout.data


def test_symbol_suggestions_prefer_one_curated_bist_option(database_path) -> None:
    with connect(database_path) as connection:
        upsert_symbol(connection, Symbol("GARAN", "GARAN", is_bist=False))
        connection.commit()

    app = create_app(Settings(database_path=database_path), OfflineProvider())
    datalist = next(
        component
        for component in app.layout._traverse()
        if getattr(component, "id", None) == "symbol-suggestions"
    )
    garan_options = [option for option in datalist.children if option.value == "GARAN"]

    assert len(garan_options) == 1
    assert "Türkiye Garanti Bankası" in garan_options[0].label
