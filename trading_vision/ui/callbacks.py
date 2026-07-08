"""Dash callbacks kept thin by delegating work to application services."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import parse_qs

from dash import ALL, Input, Output, State, ctx, dcc, html

from trading_vision.candle_gaps import CandleGapReport, find_bist_candle_gaps
from trading_vision.config import SUPPORTED_INTERVALS
from trading_vision.freshness import evaluate_data_freshness
from trading_vision.scanner_results import PatternResultFilters, ScannerResultsSnapshot
from trading_vision.services.market_data import ChartLoadResult
from trading_vision.text_safety import safe_display_text
from trading_vision.ui import ids
from trading_vision.ui.alert_views import render_alerts
from trading_vision.ui.chart_builder import build_chart, empty_chart
from trading_vision.ui.layout import detail_rows
from trading_vision.ui.overlay_selection import select_visible_patterns
from trading_vision.ui.scanner_views import diagnostic_cards, render_result_table


def register_callbacks(
    app,
    load_chart: Callable[[str, str, bool], ChartLoadResult],
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
        query = parse_qs((url_search or "").lstrip("?"))
        if isinstance(triggered, dict) and triggered.get("type") == ids.QUICK_SYMBOL_TYPE:
            requested = triggered["symbol"]
        elif triggered == ids.URL or (triggered is None and url_search):
            requested = query.get("symbol", [requested])[0]
            requested_interval = query.get("interval", [interval])[0]
            if requested_interval in SUPPORTED_INTERVALS:
                interval = requested_interval
        focus_range = _focus_range_from_query(query, requested)
        try:
            result = load_chart(requested, interval, triggered == ids.REFRESH_BUTTON)
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
            return _successful_chart_result(result, interval, provider_delay_seconds, focus_range)
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
    focus_range: tuple[datetime, datetime] | None = None,
):
    candles = result.candles
    latest = candles.iloc[-1]
    previous_close = candles.iloc[-2]["close"] if len(candles) > 1 else latest["open"]
    change_percent = (latest["close"] / previous_close - 1) * 100
    latest_time = latest["opened_at_utc"].tz_convert("Europe/Istanbul")
    latest_label = latest_time.strftime("%d %b %Y · %H:%M")
    provider_message = result.provider_message
    gap_report = (
        find_bist_candle_gaps(candles, interval) if result.symbol.is_bist else CandleGapReport()
    )
    quarantined_rows = (
        result.quality_report.quarantined_rows if result.quality_report is not None else 0
    )
    chart_meta = _chart_meta(
        result,
        latest,
        interval,
        provider_delay_seconds,
        gap_report.count,
        quarantined_rows,
    )
    visible_patterns = select_visible_patterns(candles, result.patterns)
    pattern_word = "pattern" if len(visible_patterns) == 1 else "patterns"
    status_prefix = "Cached" if result.from_cache or provider_message else "Live"
    status_text = f"{status_prefix} · {len(visible_patterns)} active {pattern_word}"
    if provider_message:
        status_class = "status-badge warning"
    elif result.from_cache:
        status_class = "status-badge neutral"
    else:
        status_class = "status-badge success"
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
    if gap_report.count:
        candle_word = "candle" if gap_report.count == 1 else "candles"
        details.append(
            html.P(
                f"{gap_report.count} missing completed {candle_word} detected inside covered "
                "BIST sessions. Pattern results may be incomplete.",
                className="inline-warning",
            )
        )
    if result.quality_report is not None and result.quality_report.has_warnings:
        details.append(
            html.P(
                f"{result.quality_report.summary()}. Invalid rows were not cached or scanned.",
                className="inline-warning",
            )
        )
    return (
        build_chart(
            candles,
            result.symbol.provider_symbol,
            interval,
            visible_patterns,
            is_bist=result.symbol.is_bist,
            focus_range=focus_range,
        ),
        result.symbol.provider_symbol,
        chart_meta,
        status_text,
        status_class,
        details,
        result.symbol.provider_symbol,
    )


def _focus_range_from_query(
    query: dict[str, list[str]],
    requested_symbol: str,
) -> tuple[datetime, datetime] | None:
    link_symbol = query.get("symbol", [""])[0]
    if not link_symbol or link_symbol.upper() != requested_symbol.upper():
        return None
    range_from = _query_time(query, "range_from")
    range_to = _query_time(query, "range_to")
    if range_from is None or range_to is None or range_to <= range_from:
        return None
    return range_from, range_to


def _query_time(query: dict[str, list[str]], key: str) -> datetime | None:
    value = query.get(key, [""])[0]
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _chart_meta(
    result: ChartLoadResult,
    latest,
    interval: str,
    provider_delay_seconds: int,
    gap_count: int = 0,
    quarantined_rows: int = 0,
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
    gap_label = ""
    if gap_count:
        gap_word = "gap" if gap_count == 1 else "gaps"
        gap_label = f" · {gap_count} data {gap_word}"
    quarantine_label = ""
    if quarantined_rows:
        row_word = "row" if quarantined_rows == 1 else "rows"
        quarantine_label = f" · {quarantined_rows} quarantined {row_word}"
    forming_label = " · forming candle" if not bool(latest.get("is_complete", True)) else ""
    return (
        f"{source} · Latest {local_time:%d %b %Y · %H:%M} · "
        f"{freshness.label}{forming_label}{gap_label}{quarantine_label}"
    )


def _source_label(source) -> str:
    normalized = str(source or "unknown").strip().lower()
    if normalized == "yahoo":
        return "Yahoo Finance"
    return safe_display_text(normalized.replace("_", " ").title())


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
