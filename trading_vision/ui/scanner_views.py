"""Scanner result table, filters, details, and diagnostics components."""

from __future__ import annotations

from dash import dcc, html

from trading_vision.config import SUPPORTED_INTERVALS, SUPPORTED_PATTERN_TYPES
from trading_vision.scanner_results import PatternResultRow
from trading_vision.ui import ids


def build_scanner_workspace() -> html.Section:
    return html.Section(
        className="scanner-workspace panel",
        children=[
            html.Div(
                [
                    html.Div(
                        [
                            html.H2("Pattern scanner"),
                            html.P("Persisted results and operational diagnostics"),
                        ]
                    ),
                    html.Div(
                        [
                            html.Button("Refresh", id=ids.SCANNER_REFRESH, className="button"),
                            html.Button("Export CSV", id=ids.SCANNER_EXPORT, className="button"),
                            dcc.Download(id=ids.SCANNER_DOWNLOAD),
                        ],
                        className="scanner-heading-actions",
                    ),
                ],
                className="scanner-heading",
            ),
            dcc.Interval(id=ids.SCANNER_POLL, interval=30_000, n_intervals=0),
            _filters(),
            html.Div(
                [
                    html.Div("0 results", id=ids.SCANNER_RESULT_COUNT, className="result-count"),
                    html.Div(id=ids.SCANNER_DIAGNOSTICS, className="diagnostic-grid"),
                ],
                className="scanner-summary-row",
            ),
            html.Div(
                id=ids.SCANNER_TABLE,
                children=html.P("No scanner results match these filters."),
                className="scanner-table-wrap",
            ),
        ],
    )


def render_result_table(rows: tuple[PatternResultRow, ...]):
    if not rows:
        return html.P("No scanner results match these filters.", className="scanner-empty")
    headings = (
        "Chart",
        "Symbol",
        "Interval",
        "Pattern",
        "Direction",
        "State",
        "Score",
        "Confirmed",
        "Boundary",
        "Target",
        "Reasons",
    )
    return html.Table(
        [
            html.Thead(html.Tr([html.Th(heading) for heading in headings])),
            html.Tbody([_table_row(row) for row in rows]),
        ],
        className="scanner-table",
    )


def diagnostic_cards(items: tuple[tuple[str, str], ...]) -> list[html.Div]:
    return [
        html.Div([html.Span(label), html.Strong(value)], className="diagnostic-card")
        for label, value in items
    ]


def _filters() -> html.Div:
    return html.Div(
        [
            _filter("Symbol", dcc.Input(id=ids.FILTER_SYMBOL, placeholder="THYAO.IS")),
            _filter(
                "Interval",
                dcc.Dropdown(
                    id=ids.FILTER_INTERVAL,
                    options=[{"label": "All", "value": ""}]
                    + [{"label": value.upper(), "value": value} for value in SUPPORTED_INTERVALS],
                    value="",
                    clearable=False,
                ),
            ),
            _filter(
                "Pattern",
                dcc.Dropdown(
                    id=ids.FILTER_PATTERN,
                    options=[{"label": "All", "value": ""}]
                    + [
                        {"label": value.replace("_", " ").title(), "value": value}
                        for value in SUPPORTED_PATTERN_TYPES
                    ],
                    value="",
                    clearable=False,
                ),
            ),
            _filter(
                "Direction",
                dcc.Dropdown(
                    id=ids.FILTER_DIRECTION,
                    options=[
                        {"label": "All", "value": ""},
                        {"label": "Bullish", "value": "bullish"},
                        {"label": "Bearish", "value": "bearish"},
                        {"label": "Neutral", "value": "neutral"},
                    ],
                    value="",
                    clearable=False,
                ),
            ),
            _filter(
                "State",
                dcc.Dropdown(
                    id=ids.FILTER_STATE,
                    options=[{"label": "All", "value": ""}]
                    + [
                        {"label": value.title(), "value": value}
                        for value in ("forming", "confirmed", "invalidated", "expired")
                    ],
                    value="",
                    clearable=False,
                ),
            ),
            _filter(
                "Minimum score",
                dcc.Input(id=ids.FILTER_SCORE, type="number", min=0, max=100, value=0),
            ),
            _filter(
                "Age",
                dcc.Dropdown(
                    id=ids.FILTER_AGE,
                    options=[
                        {"label": "7 days", "value": 7},
                        {"label": "30 days", "value": 30},
                        {"label": "90 days", "value": 90},
                        {"label": "All history", "value": 0},
                    ],
                    value=90,
                    clearable=False,
                ),
            ),
        ],
        className="scanner-filters",
    )


def _filter(label: str, control) -> html.Label:
    return html.Label([html.Span(label), control], className="scanner-filter")


def _table_row(row: PatternResultRow) -> html.Tr:
    confirmed = row.confirmed_at or row.started_at
    reason_preview = row.reasons[0] if row.reasons else "No score reasons"
    return html.Tr(
        [
            html.Td(dcc.Link("Open", href=row.app_link)),
            html.Td(row.provider_symbol),
            html.Td(row.interval.upper()),
            html.Td(row.pattern_type.replace("_", " ").title()),
            html.Td(row.direction),
            html.Td(row.state),
            html.Td(f"{row.score:.1f}"),
            html.Td(confirmed.strftime("%Y-%m-%d %H:%M")),
            html.Td(f"{row.boundary_price:,.4f}"),
            html.Td(f"{row.target_price:,.4f}" if row.target_price is not None else "—"),
            html.Td(
                html.Details(
                    [
                        html.Summary(reason_preview),
                        html.Ul([html.Li(reason) for reason in row.reasons]),
                    ]
                )
            ),
        ]
    )
