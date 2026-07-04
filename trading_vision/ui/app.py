"""Application factory and command-line entry point."""

from __future__ import annotations

from dash import Dash

from trading_vision.config import PROJECT_ROOT, Settings, load_settings
from trading_vision.database import connection_scope, initialize_database
from trading_vision.models import Symbol
from trading_vision.providers.yahoo import YahooFinanceProvider
from trading_vision.repositories import import_symbol_catalog, seed_symbols
from trading_vision.scanner_repository import get_heartbeat
from trading_vision.services.market_data import MarketDataService
from trading_vision.services.pattern_scan import PatternScanService
from trading_vision.ui.callbacks import register_callbacks
from trading_vision.ui.layout import build_layout
from trading_vision.ui.scanner_status import scanner_status_text

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
    with connection_scope(settings.database_path) as connection:
        import_symbol_catalog(connection, CATALOG_PATH)
        seed_symbols(connection, FALLBACK_SYMBOLS)
        scanner_status = scanner_status_text(get_heartbeat(connection))

    data_provider = provider or YahooFinanceProvider()

    def load_chart(symbol_query: str, interval: str):
        with connection_scope(settings.database_path) as connection:
            market_data = MarketDataService(
                connection=connection,
                provider=data_provider,
                candle_limit=settings.chart_candle_limit,
            )
            result = market_data.load(symbol_query, interval)
            if not result.candles.empty:
                pattern_scan = PatternScanService(connection)
                scan_result = pattern_scan.scan(result.symbol, interval, result.candles)
                result.patterns = scan_result.matches
            return result

    app = Dash(
        __name__,
        title="Trading Vision",
        update_title="Loading market data…",
        suppress_callback_exceptions=False,
    )
    app.layout = build_layout(settings, scanner_status)
    register_callbacks(app, load_chart)
    return app


def main() -> None:
    settings = load_settings()
    app = create_app(settings)
    app.run(host=settings.host, port=settings.port, debug=settings.debug)


if __name__ == "__main__":
    main()
