"""Application factory and command-line entry point."""

from __future__ import annotations

from dash import Dash

from trading_vision.alert_repository import (
    acknowledge_alert,
    acknowledge_all_alerts,
    list_recent_alerts,
    mute_alert_pattern,
    unread_alert_count,
)
from trading_vision.config import PROJECT_ROOT, Settings, load_settings
from trading_vision.database import connection_scope, initialize_database
from trading_vision.models import Symbol
from trading_vision.providers.yahoo import YahooFinanceProvider
from trading_vision.repositories import import_symbol_catalog, search_symbols, seed_symbols
from trading_vision.scanner_repository import get_heartbeat
from trading_vision.services.chart_load_cache import ChartLoadCooldown
from trading_vision.services.market_data import MarketDataService
from trading_vision.services.pattern_scan import PatternScanService
from trading_vision.services.scanner_results import ScannerResultsService
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
        symbols = _unique_display_symbols(search_symbols(connection, limit=10_000))

    data_provider = provider or YahooFinanceProvider()
    chart_load_cooldown = ChartLoadCooldown(settings.provider_cooldown_seconds)

    def load_chart(symbol_query: str, interval: str, force_refresh: bool = False):
        def load_from_provider():
            with connection_scope(settings.database_path) as connection:
                market_data = MarketDataService(
                    connection=connection,
                    provider=data_provider,
                    candle_limit=settings.chart_candle_limit,
                    provider_delay_seconds=settings.provider_delay_seconds,
                )
                result = market_data.load(symbol_query, interval)
                if not result.candles.empty:
                    pattern_scan = PatternScanService(
                        connection,
                        minimum_alert_score=settings.minimum_alert_score,
                        alert_pattern_types=settings.alert_pattern_types,
                    )
                    scan_result = pattern_scan.scan(result.symbol, interval, result.candles)
                    result.patterns = scan_result.matches
                return result

        return chart_load_cooldown.get_or_load(
            symbol_query,
            interval,
            load_from_provider,
            force=force_refresh,
        )

    def update_alerts(action: str | None, alert_id: int | None):
        with connection_scope(settings.database_path) as connection:
            if action == "acknowledge" and alert_id is not None:
                acknowledge_alert(connection, alert_id)
            elif action == "acknowledge_all":
                acknowledge_all_alerts(connection)
            elif action == "mute" and alert_id is not None:
                mute_alert_pattern(connection, alert_id)
            return unread_alert_count(connection), tuple(list_recent_alerts(connection))

    def load_scanner(filters):
        with connection_scope(settings.database_path) as connection:
            return ScannerResultsService(connection, settings).load(filters)

    def export_scanner(filters):
        with connection_scope(settings.database_path) as connection:
            return ScannerResultsService(connection, settings).export_csv(filters)

    app = Dash(
        __name__,
        title="Trading Vision",
        update_title="Loading market data…",
        suppress_callback_exceptions=False,
    )
    app.layout = build_layout(settings, scanner_status, symbols)
    register_callbacks(
        app,
        load_chart,
        update_alerts,
        load_scanner,
        export_scanner,
        settings.provider_delay_seconds,
    )
    return app


def _unique_display_symbols(symbols: list[Symbol]) -> tuple[Symbol, ...]:
    unique: list[Symbol] = []
    seen: set[str] = set()
    for symbol in symbols:
        key = symbol.display_symbol.upper()
        if key in seen:
            continue
        seen.add(key)
        unique.append(symbol)
    return tuple(unique)


def main() -> None:
    settings = load_settings()
    app = create_app(settings)
    app.run(host=settings.host, port=settings.port, debug=settings.debug)


if __name__ == "__main__":
    main()
