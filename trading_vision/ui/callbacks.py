"""Dash callbacks kept thin by delegating work to application services."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import parse_qs

from dash import ALL, Input, Output, State, ctx, dcc, html

from trading_vision.freshness import evaluate_data_freshness
from trading_vision.scanner_results import PatternResultFilters, ScannerResultsSnapshot
from trading_vision.services.market_data import ChartLoadResult
from trading_vision.ui import ids
from trading_vision.ui.alert_views import render_alerts
from trading_vision.ui.chart_builder import build_chart, empty_chart
from trading_vision.ui.layout import detail_rows
from trading_vision.ui.overlay_selection import select_visible_patterns
from trading_vision.ui.scanner_views import diagnostic_cards, render_result_table


def register_callbacks(
    app,
    load_chart: Callable[[str, str], ChartLoadResult],
    update_alerts: Callable[[str | None, int | None], tuple[int, tuple]],
    load_scanner: Callable[[PatternResultFilters], ScannerResultsSnapshot],
    export_scanner: Callable[[PatternResultFilters], str],
    provider_delay_seconds: int,
) -> None:
    @app.callback(
        Output(ids.CHART, "figure"),
        Output(ids.CHART_TITLE, "children"),
        Output(ids.CHART_META, "children"),
        Output(ids.STATUS, "children"),
        Output(ids.STATUS, "className"),
        Output(ids.DETAILS, "children"),
        Output(ids.SYMBOL_INPUT, "value"),
        Input(ids.LOAD_BUTTON, "n_clicks"),
        Input(ids.SYMBOL_INPUT, "n_submit"),
        Input(ids.REFRESH_BUTTON, "n_clicks"),
        Input(ids.INTERVAL_SELECT, "value"),
        Input({"type": ids.QUICK_SYMBOL_TYPE, "symbol": ALL}, "n_clicks"),
        Input(ids.URL, "search"),
        State(ids.SYMBOL_INPUT, "value"),
    )
    def update_chart(
        _load,
        _submit,
        _refresh,
        interval,
        _quick_clicks,
        url_search,
        typed_symbol,
    ):
        requested = typed_symbol or ""
        triggered = ctx.triggered_id
        if isinstance(triggered, dict) and triggered.get("type") == ids.QUICK_SYMBOL_TYPE:
            requested = triggered["symbol"]
        elif triggered == ids.URL or (triggered is None and url_search):
            query = parse_qs((url_search or "").lstrip("?"))
            requested = query.get("symbol", [requested])[0]
            requested_interval = query.get("interval", [interval])[0]
            if requested_interval in {"1d", "1h", "15m", "5m"}:
                interval = requested_interval
        try:
            result = load_chart(requested, interval)
            if result.candles.empty:
                message = result.provider_message or "No candles returned"
                return (
                    empty_chart(message),
                    result.symbol.provider_symbol,
                    "No latest candle available",
                    "No data",
                    "status-badge error",
                    [html.P(message, className="inline-error")],
                    result.symbol.provider_symbol,
                )
            return _successful_chart_result(result, interval, provider_delay_seconds)
        except Exception as error:
            message = str(error) or "Unable to load this symbol"
            return (
                empty_chart(message),
                requested.upper() or "Market chart",
                "Unable to determine data freshness",
                "Load failed",
                "status-badge error",
                [html.P(message, className="inline-error")],
                requested,
            )

    @app.callback(
        Output(ids.APP_ROOT, "className"),
        Output(ids.THEME_BUTTON, "children"),
        Input(ids.THEME_BUTTON, "n_clicks"),
    )
    def toggle_theme(clicks):
        if clicks and clicks % 2:
            return "app-shell theme-light", "Dark mode"
        return "app-shell theme-dark", "Light mode"

    @app.callback(
        Output(ids.ALERT_COUNT, "children"),
        Output(ids.ALERT_LIST, "children"),
        Input(ids.ALERT_POLL, "n_intervals"),
        Input(ids.ALERT_ACK_ALL, "n_clicks"),
        Input({"type": ids.ALERT_ACK_TYPE, "alert_id": ALL}, "n_clicks"),
        Input({"type": ids.ALERT_MUTE_TYPE, "alert_id": ALL}, "n_clicks"),
    )
    def refresh_alerts(_poll, _ack_all, _ack_clicks, _mute_clicks):
        action = None
        alert_id = None
        triggered = ctx.triggered_id
        if triggered == ids.ALERT_ACK_ALL:
            action = "acknowledge_all"
        elif isinstance(triggered, dict):
            alert_id = int(triggered["alert_id"])
            if triggered.get("type") == ids.ALERT_ACK_TYPE:
                action = "acknowledge"
            elif triggered.get("type") == ids.ALERT_MUTE_TYPE:
                action = "mute"
        unread, events = update_alerts(action, alert_id)
        return str(unread), render_alerts(events)

    @app.callback(
        Output(ids.SCANNER_TABLE, "children"),
        Output(ids.SCANNER_DIAGNOSTICS, "children"),
        Output(ids.SCANNER_RESULT_COUNT, "children"),
        Input(ids.SCANNER_POLL, "n_intervals"),
        Input(ids.SCANNER_REFRESH, "n_clicks"),
        Input(ids.FILTER_SYMBOL, "value"),
        Input(ids.FILTER_INTERVAL, "value"),
        Input(ids.FILTER_PATTERN, "value"),
        Input(ids.FILTER_DIRECTION, "value"),
        Input(ids.FILTER_STATE, "value"),
        Input(ids.FILTER_SCORE, "value"),
        Input(ids.FILTER_AGE, "value"),
    )
    def refresh_scanner(
        _poll,
        _refresh,
        symbol,
        interval,
        pattern_type,
        direction,
        state,
        minimum_score,
        lookback_days,
    ):
        filters = _result_filters(
            symbol,
            interval,
            pattern_type,
            direction,
            state,
            minimum_score,
            lookback_days,
        )
        snapshot = load_scanner(filters)
        return (
            render_result_table(snapshot.rows),
            diagnostic_cards(snapshot.diagnostics),
            f"{len(snapshot.rows):,} results",
        )

    @app.callback(
        Output(ids.SCANNER_DOWNLOAD, "data"),
        Input(ids.SCANNER_EXPORT, "n_clicks"),
        State(ids.FILTER_SYMBOL, "value"),
        State(ids.FILTER_INTERVAL, "value"),
        State(ids.FILTER_PATTERN, "value"),
        State(ids.FILTER_DIRECTION, "value"),
        State(ids.FILTER_STATE, "value"),
        State(ids.FILTER_SCORE, "value"),
        State(ids.FILTER_AGE, "value"),
        prevent_initial_call=True,
    )
    def export_scanner_csv(
        _clicks,
        symbol,
        interval,
        pattern_type,
        direction,
        state,
        minimum_score,
        lookback_days,
    ):
        filters = _result_filters(
            symbol,
            interval,
            pattern_type,
            direction,
            state,
            minimum_score,
            lookback_days,
        )
        return dcc.send_string(export_scanner(filters), "trading-vision-patterns.csv")


def _successful_chart_result(
    result: ChartLoadResult,
    interval: str,
    provider_delay_seconds: int,
):
    candles = result.candles
    latest = candles.iloc[-1]
    previous_close = candles.iloc[-2]["close"] if len(candles) > 1 else latest["open"]
    change_percent = (latest["close"] / previous_close - 1) * 100
    latest_time = latest["opened_at_utc"].tz_convert("Europe/Istanbul")
    latest_label = latest_time.strftime("%d %b %Y · %H:%M")
    provider_message = result.provider_message
    chart_meta = _chart_meta(result, latest, interval, provider_delay_seconds)
    visible_patterns = select_visible_patterns(candles, result.patterns)
    pattern_word = "pattern" if len(visible_patterns) == 1 else "patterns"
    status_text = (
        "Cached" if provider_message else f"Live · {len(visible_patterns)} active {pattern_word}"
    )
    status_class = "status-badge warning" if provider_message else "status-badge success"
    details = detail_rows(
        symbol=result.symbol.provider_symbol,
        name=result.symbol.name,
        interval=interval,
        candle_count=len(candles),
        latest=latest_label,
        close=f"{latest['close']:,.2f} {result.symbol.currency or ''}".strip(),
        change=f"{change_percent:+.2f}%",
        patterns=visible_patterns,
    )
    if provider_message:
        details.append(html.P(provider_message, className="inline-warning"))
    return (
        build_chart(candles, result.symbol.provider_symbol, interval, visible_patterns),
        result.symbol.provider_symbol,
        chart_meta,
        status_text,
        status_class,
        details,
        result.symbol.provider_symbol,
    )


def _chart_meta(
    result: ChartLoadResult,
    latest,
    interval: str,
    provider_delay_seconds: int,
) -> str:
    opened_at = latest["opened_at_utc"].to_pydatetime()
    freshness = evaluate_data_freshness(
        latest_candle_at=opened_at,
        interval=interval,
        now=datetime.now(UTC),
        is_bist=result.symbol.is_bist,
        provider_delay_seconds=provider_delay_seconds,
    )
    source = _source_label(latest.get("source"))
    local_time = latest["opened_at_utc"].tz_convert("Europe/Istanbul")
    return f"{source} · Latest {local_time:%d %b %Y · %H:%M} · {freshness.label}"


def _source_label(source) -> str:
    normalized = str(source or "unknown").strip().lower()
    if normalized == "yahoo":
        return "Yahoo Finance"
    return normalized.replace("_", " ").title()


def _result_filters(
    symbol,
    interval,
    pattern_type,
    direction,
    state,
    minimum_score,
    lookback_days,
) -> PatternResultFilters:
    return PatternResultFilters(
        symbol=(symbol or "").strip(),
        interval=interval or "",
        pattern_type=pattern_type or "",
        direction=direction or "",
        state=state or "",
        minimum_score=float(minimum_score or 0),
        lookback_days=int(lookback_days or 0),
    )
