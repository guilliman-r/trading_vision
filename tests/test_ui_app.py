from trading_vision.config import Settings
from trading_vision.providers.base import MarketDataProvider
from trading_vision.ui.app import create_app


class OfflineProvider(MarketDataProvider):
    pass


def test_app_factory_builds_layout(database_path) -> None:
    settings = Settings(database_path=database_path)
    app = create_app(settings=settings, provider=OfflineProvider())
    assert app.title == "Trading Vision"
    assert app.layout.id == "app-root"
