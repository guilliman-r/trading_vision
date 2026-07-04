"""Dash callbacks kept thin by delegating work to application services."""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import parse_qs

from dash import ALL, Input, Output, State, ctx, html

from trading_vision.services.market_data import ChartLoadResult
from trading_vision.ui import ids
from trading_vision.ui.alert_views import render_alerts
from trading_vision.ui.chart_builder import build_chart, empty_chart
from trading_vision.ui.layout import detail_rows


def register_callbacks(
    app,
    load_chart: Callable[[str, str], ChartLoadResult],
    update_alerts: Callable[[str | None, int | None], tuple[int, tuple]],
) -> None:
    @app.callback(
        Output(ids.CHART, "figure"),
        Output(ids.CHART_TITLE, "children"),
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
                    "No data",
                    "status-badge error",
                    [html.P(message, className="inline-error")],
                    result.symbol.provider_symbol,
                )
            return _successful_chart_result(result, interval)
        except Exception as error:
            message = str(error) or "Unable to load this symbol"
            return (
                empty_chart(message),
                requested.upper() or "Market chart",
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


def _successful_chart_result(result: ChartLoadResult, interval: str):
    candles = result.candles
    latest = candles.iloc[-1]
    previous_close = candles.iloc[-2]["close"] if len(candles) > 1 else latest["open"]
    change_percent = (latest["close"] / previous_close - 1) * 100
    latest_time = latest["opened_at_utc"].tz_convert("Europe/Istanbul")
    latest_label = latest_time.strftime("%d %b %Y · %H:%M")
    provider_message = result.provider_message
    active_patterns = [pattern for pattern in result.patterns if pattern.state != "expired"]
    status_text = "Cached" if provider_message else f"Live · {len(active_patterns)} patterns"
    status_class = "status-badge warning" if provider_message else "status-badge success"
    details = detail_rows(
        symbol=result.symbol.provider_symbol,
        name=result.symbol.name,
        interval=interval,
        candle_count=len(candles),
        latest=latest_label,
        close=f"{latest['close']:,.2f} {result.symbol.currency or ''}".strip(),
        change=f"{change_percent:+.2f}%",
        patterns=result.patterns,
    )
    if provider_message:
        details.append(html.P(provider_message, className="inline-warning"))
    return (
        build_chart(candles, result.symbol.provider_symbol, interval, result.patterns),
        result.symbol.provider_symbol,
        status_text,
        status_class,
        details,
        result.symbol.provider_symbol,
    )
