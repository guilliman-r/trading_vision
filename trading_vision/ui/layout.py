"""Visible application structure; callbacks live elsewhere."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

from dash import dcc, html

from trading_vision.config import SUPPORTED_INTERVALS, Settings
from trading_vision.models import PatternMatch, Symbol
from trading_vision.pattern_focus import pattern_focus_range
from trading_vision.text_safety import safe_display_text
from trading_vision.ui import ids
from trading_vision.ui.chart_builder import CHART_CONFIG, CHART_HEIGHT, empty_chart
from trading_vision.ui.scanner_views import build_scanner_workspace

QUICK_SYMBOLS = ("THYAO", "GARAN", "ASELS", "TUPRS", "BIMAS", "EREGL")


def build_layout(
    settings: Settings,
    scanner_status: str = "Scanner not started",
    symbols: tuple[Symbol, ...] = (),
) -> html.Div:
    return html.Div(
        id=ids.APP_ROOT,
        className="app-shell theme-dark",
        children=[
            dcc.Location(id=ids.URL, refresh=False),
            dcc.Interval(id=ids.ALERT_POLL, interval=15_000, n_intervals=0),
            _top_bar(settings, symbols),
            html.Main(
                className="workspace",
                children=[
                    _watchlist(scanner_status),
                    _chart_panel(),
                    _details_panel(),
                ],
            ),
            build_scanner_workspace(),
        ],
    )


def _top_bar(settings: Settings, symbols: tuple[Symbol, ...]) -> html.Header:
    return html.Header(
        className="top-bar",
        children=[
            html.Div(
                className="brand",
                children=[
                    html.Div("TV", className="brand-mark"),
                    html.Div([html.Strong("Trading Vision"), html.Span("Pattern radar")]),
                ],
            ),
            html.Div(
                className="symbol-search",
                children=[
                    dcc.Input(
                        id=ids.SYMBOL_INPUT,
                        value=settings.default_symbol,
                        type="text",
                        list=ids.SYMBOL_SUGGESTIONS,
                        debounce=False,
                        placeholder="THYAO, AAPL, BTC-USD…",
                        autoComplete="off",
                    ),
                    html.Datalist(
                        id=ids.SYMBOL_SUGGESTIONS,
                        children=[
                            html.Option(
                                value=symbol.display_symbol,
                                label=_symbol_option_label(symbol),
                            )
                            for symbol in symbols
                        ],
                    ),
                    html.Button("Load", id=ids.LOAD_BUTTON, className="button primary"),
                ],
            ),
            dcc.Dropdown(
                id=ids.INTERVAL_SELECT,
                options=[{"label": value.upper(), "value": value} for value in SUPPORTED_INTERVALS],
                value=settings.default_interval,
                clearable=False,
                searchable=False,
                className="interval-select",
            ),
            html.Button("Refresh", id=ids.REFRESH_BUTTON, className="button secondary"),
            html.Div(
                [html.Span("Alerts"), html.Strong("0", id=ids.ALERT_COUNT)],
                className="alert-indicator",
            ),
            html.Button("Light mode", id=ids.THEME_BUTTON, className="button ghost"),
        ],
    )


def _symbol_option_label(symbol: Symbol) -> str:
    display_symbol = safe_display_text(symbol.display_symbol, max_length=40)
    if not symbol.name:
        return display_symbol
    return f"{display_symbol} · {safe_display_text(symbol.name)}"


def _watchlist(scanner_status: str) -> html.Aside:
    buttons = [
        html.Button(
            [html.Strong(symbol), html.Span("BIST")],
            id={"type": ids.QUICK_SYMBOL_TYPE, "symbol": symbol},
            className="watchlist-item",
        )
        for symbol in QUICK_SYMBOLS
    ]
    return html.Aside(
        className="left-panel panel",
        children=[
            html.Div([html.H2("Watchlist"), html.Span("Quick access")], className="panel-heading"),
            html.Div(buttons, className="watchlist"),
            html.Div(
                [html.Span(className="pulse-dot"), html.Span("Yahoo Finance data")],
                className="source-note",
            ),
            html.Div(
                [html.Span(className="pulse-dot"), html.Span(scanner_status)],
                id=ids.SCANNER_STATUS,
                className="source-note",
            ),
        ],
    )


def _chart_panel() -> html.Section:
    return html.Section(
        className="chart-panel panel",
        children=[
            html.Div(
                [
                    html.Div(
                        [
                            html.H1("Market chart", id=ids.CHART_TITLE),
                            html.P("Waiting for data", id=ids.CHART_META),
                        ]
                    ),
                    html.Div("Ready", id=ids.STATUS, className="status-badge neutral"),
                ],
                className="chart-heading",
            ),
            dcc.Loading(
                type="circle",
                color="#4da3ff",
                children=dcc.Graph(
                    id=ids.CHART,
                    figure=empty_chart("Loading market data…"),
                    config=CHART_CONFIG,
                    responsive=True,
                    className="chart",
                    style={"height": f"{CHART_HEIGHT}px", "width": "100%"},
                ),
            ),
        ],
    )


def _details_panel() -> html.Aside:
    return html.Aside(
        className="right-panel panel",
        children=[
            html.Div([html.H2("Instrument"), html.Span("Snapshot")], className="panel-heading"),
            html.Div(id=ids.DETAILS, className="details", children=_empty_details()),
            html.Div(
                [
                    html.Div(
                        [
                            html.H2("Alerts"),
                            html.Button(
                                "Acknowledge all",
                                id=ids.ALERT_ACK_ALL,
                                className="alert-ack-all",
                            ),
                        ],
                        className="alert-center-heading",
                    ),
                    html.Div(
                        id=ids.ALERT_LIST,
                        children=[html.P("No pattern alerts yet.", className="alert-empty")],
                    ),
                ],
                className="alert-center",
            ),
        ],
    )


def _empty_details() -> list[html.Div]:
    return [
        _detail_row("Symbol", "—"),
        _detail_row("Candles", "—"),
        _detail_row("Latest", "—"),
        _pattern_empty("Load a symbol to scan completed candles."),
    ]


def detail_rows(
    symbol: str,
    name: str | None,
    interval: str,
    candle_count: int,
    latest: str,
    close: str,
    change: str,
    patterns: tuple[PatternMatch, ...] = (),
) -> list[html.Div]:
    rows = [
        _detail_row("Symbol", safe_display_text(symbol, max_length=40)),
        _detail_row("Name", safe_display_text(name, fallback="Yahoo instrument")),
        _detail_row("Interval", safe_display_text(interval.upper(), max_length=10)),
        _detail_row("Candles", f"{candle_count:,}"),
        _detail_row("Latest", latest),
        _detail_row("Close", close),
        _detail_row("Bar change", change),
        _pattern_summary(symbol, interval, patterns),
    ]
    return rows


def _detail_row(label: str, value: str) -> html.Div:
    return html.Div(
        [html.Span(label), html.Strong(safe_display_text(value))],
        className="detail-row",
    )


def _pattern_summary(symbol: str, interval: str, patterns: tuple[PatternMatch, ...]) -> html.Div:
    if not patterns:
        return _pattern_empty("No forming or recently confirmed patterns in this window.")
    priority = {"forming": 0, "confirmed": 1}
    active = sorted(patterns, key=lambda pattern: (priority.get(pattern.state, 9), -pattern.score))
    cards = [_pattern_card(symbol, interval, pattern) for pattern in active]
    return html.Div(
        [
            html.Div(
                [html.H3("Pattern engine"), html.Div(str(len(active)), className="pattern-count")],
                className="pattern-section-heading",
            ),
            *cards,
        ],
        className="pattern-summary",
    )


def _pattern_card(symbol: str, interval: str, pattern: PatternMatch) -> dcc.Link:
    title = pattern.pattern_type.replace("_", " ").title()
    return dcc.Link(
        [
            html.Div(
                [
                    html.Strong(title),
                    html.Div(
                        [
                            html.Span(pattern.state, className=f"pattern-state {pattern.state}"),
                            html.Span("Zoom", className="pattern-zoom-chip"),
                        ],
                        className="pattern-card-actions",
                    ),
                ],
                className="pattern-card-heading",
            ),
            html.Div(
                _pattern_metrics(pattern),
                className="pattern-metrics",
            ),
            html.Ul(
                [html.Li(safe_display_text(reason, max_length=240)) for reason in pattern.reasons],
                className="pattern-reasons",
            ),
        ],
        href=_pattern_card_href(symbol, interval, pattern),
        title=f"Zoom chart to {title}",
        className="pattern-card pattern-card-link",
    )


def _pattern_metrics(pattern: PatternMatch) -> list[html.Span]:
    metrics = [
        html.Span(f"Score {pattern.score:.0f}"),
        html.Span(f"Level {pattern.boundary_price:,.2f}"),
        html.Span(
            f"Target {pattern.target_price:,.2f}"
            if pattern.target_price is not None
            else "No target"
        ),
    ]
    if pattern.invalidation_price is not None:
        metrics.append(html.Span(f"Invalidation {pattern.invalidation_price:,.2f}"))
    risk_reward = _pattern_reward_risk(pattern)
    if risk_reward is not None:
        metrics.append(html.Span(f"R/R {risk_reward:.2f}"))
    return metrics


def _pattern_reward_risk(pattern: PatternMatch) -> float | None:
    if pattern.target_price is None or pattern.invalidation_price is None:
        return None
    if pattern.direction == "bullish":
        reward = pattern.target_price - pattern.boundary_price
        risk = pattern.boundary_price - pattern.invalidation_price
    elif pattern.direction == "bearish":
        reward = pattern.boundary_price - pattern.target_price
        risk = pattern.invalidation_price - pattern.boundary_price
    else:
        return None
    if reward <= 0 or risk <= 0:
        return None
    return reward / risk


def _pattern_card_href(symbol: str, interval: str, pattern: PatternMatch) -> str:
    range_from, range_to = pattern_focus_range(
        interval,
        pattern.started_at,
        pattern.confirmed_at,
        _pattern_last_seen_at(pattern),
    )
    query = urlencode(
        {
            "symbol": symbol,
            "interval": interval,
            "pattern": pattern.pattern_type,
            "range_from": range_from.isoformat(),
            "range_to": range_to.isoformat(),
        }
    )
    return f"/?{query}"


def _pattern_last_seen_at(pattern: PatternMatch) -> datetime:
    timestamps = [pattern.started_at]
    timestamps.extend(point.occurred_at for point in pattern.points)
    if pattern.ended_at is not None:
        timestamps.append(pattern.ended_at)
    if pattern.confirmed_at is not None:
        timestamps.append(pattern.confirmed_at)
    return max(timestamps)


def _pattern_empty(message: str) -> html.Div:
    return html.Div(
        [html.H3("Pattern engine"), html.P(message)],
        className="pattern-placeholder",
    )
