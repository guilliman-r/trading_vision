from datetime import UTC, datetime

from trading_vision.config import Settings
from trading_vision.database import connect
from trading_vision.providers.base import MarketDataProvider
from trading_vision.scanner_repository import update_heartbeat
from trading_vision.ui.app import create_app


class OfflineProvider(MarketDataProvider):
    pass


def test_app_factory_builds_layout(database_path) -> None:
    settings = Settings(database_path=database_path)
    app = create_app(settings=settings, provider=OfflineProvider())
    assert app.title == "Trading Vision"
    assert app.layout.id == "app-root"


def test_layout_displays_persisted_scanner_heartbeat(database_path) -> None:
    moment = datetime(2026, 7, 4, 12, tzinfo=UTC)
    with connect(database_path) as connection:
        update_heartbeat(connection, "sleeping", 123, moment, moment)
        connection.commit()
    app = create_app(Settings(database_path=database_path), OfflineProvider())
    client = app.server.test_client()
    layout = client.get("/_dash-layout")
    assert b"Scanner Sleeping" in layout.data
