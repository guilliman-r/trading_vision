"""Application factory and command-line entry point."""

from __future__ import annotations

from dash import Dash

from trading_vision.config import PROJECT_ROOT, Settings, load_settings
from trading_vision.database import connect, initialize_database
from trading_vision.models import Symbol
from trading_vision.providers.yahoo import YahooFinanceProvider
from trading_vision.repositories import import_symbol_catalog, seed_symbols
from trading_vision.services.market_data import MarketDataService
from trading_vision.ui.callbacks import register_callbacks
from trading_vision.ui.layout import build_layout

CATALOG_PATH = PROJECT_ROOT / "data" / "catalogs" / "bist_symbols.csv"
FALLBACK_SYMBOLS = (
    Symbol("THYAO", "THYAO.IS", "Türk Hava Yolları", "XIST", "TRY", True),
    Symbol("GARAN", "GARAN.IS", "Türkiye Garanti Bankası", "XIST", "TRY", True),
    Symbol("ASELS", "ASELS.IS", "Aselsan", "XIST", "TRY", True),
    Symbol("TUPRS", "TUPRS.IS", "Tüpraş", "XIST", "TRY", True),
    Symbol("BIMAS", "BIMAS.IS", "BİM Birleşik Mağazalar", "XIST", "TRY", True),
    Symbol("EREGL", "EREGL.IS", "Ereğli Demir ve Çelik", "XIST", "TRY", True),
)


def create_app(settings: Settings | None = None, provider=None) -> Dash:
    settings = settings or load_settings()
    initialize_database(settings.database_path)
    connection = connect(settings.database_path)
    imported = import_symbol_catalog(connection, CATALOG_PATH)
    if imported == 0:
        seed_symbols(connection, FALLBACK_SYMBOLS)
    connection.commit()

    market_data = MarketDataService(
        connection=connection,
        provider=provider or YahooFinanceProvider(),
        candle_limit=settings.chart_candle_limit,
    )
    app = Dash(
        __name__,
        title="Trading Vision",
        update_title="Loading market data…",
        suppress_callback_exceptions=False,
    )
    app.layout = build_layout(settings)
    register_callbacks(app, market_data.load)
    return app


def main() -> None:
    settings = load_settings()
    app = create_app(settings)
    app.run(host=settings.host, port=settings.port, debug=settings.debug)


if __name__ == "__main__":
    main()
