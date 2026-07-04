"""Visible application structure; callbacks live elsewhere."""

from __future__ import annotations

from dash import dcc, html

from trading_vision.config import SUPPORTED_INTERVALS, Settings
from trading_vision.ui import ids
from trading_vision.ui.chart_builder import CHART_CONFIG, empty_chart

QUICK_SYMBOLS = ("THYAO", "GARAN", "ASELS", "TUPRS", "BIMAS", "EREGL")


def build_layout(settings: Settings) -> html.Div:
    return html.Div(
        id=ids.APP_ROOT,
        className="app-shell theme-dark",
        children=[
            _top_bar(settings),
            html.Main(
                className="workspace",
                children=[
                    _watchlist(),
                    _chart_panel(),
                    _details_panel(),
                ],
            ),
        ],
    )


def _top_bar(settings: Settings) -> html.Header:
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
                        debounce=False,
                        placeholder="THYAO, AAPL, BTC-USD…",
                        autoComplete="off",
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
            html.Button("Light mode", id=ids.THEME_BUTTON, className="button ghost"),
        ],
    )


def _watchlist() -> html.Aside:
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
        ],
    )


def _chart_panel() -> html.Section:
    return html.Section(
        className="chart-panel panel",
        children=[
            html.Div(
                [
                    html.Div(
                        [html.H1("Market chart", id=ids.CHART_TITLE), html.P("Waiting for data")]
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
                    className="chart",
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
                    html.H3("Pattern engine"),
                    html.Div("NEXT", className="coming-soon-pill"),
                    html.P(
                        "Closed-candle pattern detection will plug into this panel "
                        "without changing "
                        "the chart or provider layers."
                    ),
                ],
                className="pattern-placeholder",
            ),
        ],
    )


def _empty_details() -> list[html.Div]:
    return [_detail_row("Symbol", "—"), _detail_row("Candles", "—"), _detail_row("Latest", "—")]


def detail_rows(
    symbol: str,
    name: str | None,
    interval: str,
    candle_count: int,
    latest: str,
    close: str,
    change: str,
) -> list[html.Div]:
    rows = [
        _detail_row("Symbol", symbol),
        _detail_row("Name", name or "Yahoo instrument"),
        _detail_row("Interval", interval.upper()),
        _detail_row("Candles", f"{candle_count:,}"),
        _detail_row("Latest", latest),
        _detail_row("Close", close),
        _detail_row("Bar change", change),
    ]
    return rows


def _detail_row(label: str, value: str) -> html.Div:
    return html.Div([html.Span(label), html.Strong(value)], className="detail-row")
