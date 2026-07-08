"""Pure Plotly figure construction with no network or database calls."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from trading_vision.models import PatternMatch
from trading_vision.ui.pattern_overlays import add_pattern_overlays
from trading_vision.ui.range_breaks import bist_range_breaks

DEFAULT_VISIBLE_CANDLES = 180
CHART_HEIGHT = 680


def build_chart(
    candles: pd.DataFrame,
    symbol: str,
    interval: str,
    patterns: tuple[PatternMatch, ...] = (),
    is_bist: bool = False,
    focus_range: tuple[datetime, datetime] | None = None,
) -> go.Figure:
    if candles.empty:
        return empty_chart("No chart data is available")

    colors = candles["close"].ge(candles["open"]).map({True: "#19c37d", False: "#f05a67"})
    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=[0.78, 0.22],
    )
    figure.add_trace(
        go.Candlestick(
            x=candles["opened_at_utc"],
            open=candles["open"],
            high=candles["high"],
            low=candles["low"],
            close=candles["close"],
            hovertext=_candle_hover_text(candles, symbol),
            hoverinfo="text",
            increasing_line_color="#19c37d",
            decreasing_line_color="#f05a67",
            name=symbol,
        ),
        row=1,
        col=1,
    )
    add_pattern_overlays(figure, candles, patterns)
    figure.add_trace(
        go.Bar(
            x=candles["opened_at_utc"],
            y=candles["volume"],
            marker_color=colors,
            marker_opacity=0.62,
            name="Volume",
            hovertemplate="Volume %{y:,.0f}<extra></extra>",
        ),
        row=2,
        col=1,
    )
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0b0f17",
        plot_bgcolor="#0b0f17",
        font_color="#aab4c3",
        autosize=True,
        height=CHART_HEIGHT,
        margin={"l": 14, "r": 58, "t": 12, "b": 28},
        showlegend=False,
        hovermode="x",
        dragmode="zoom",
        uirevision=f"{symbol}:{interval}",
        xaxis_rangeslider_visible=False,
        modebar={"bgcolor": "rgba(11, 15, 23, 0.88)", "color": "#8d98a8"},
        newshape={"line": {"color": "#4da3ff", "width": 2}},
    )
    figure.update_xaxes(
        showgrid=True,
        gridcolor="#18202d",
        zeroline=False,
        showspikes=True,
        spikecolor="#607086",
        spikethickness=1,
    )
    if is_bist:
        figure.update_xaxes(rangebreaks=bist_range_breaks(candles, interval))
    figure.update_yaxes(
        showgrid=True,
        gridcolor="#18202d",
        zeroline=False,
        side="right",
        fixedrange=False,
    )
    _focus_chart_on_candles(figure, candles, focus_range)
    return figure


def _candle_hover_text(candles: pd.DataFrame, symbol: str) -> list[str]:
    previous_closes = candles["close"].shift(1).fillna(candles["open"])
    labels: list[str] = []
    for candle, previous_close in zip(
        candles.itertuples(index=False), previous_closes, strict=True
    ):
        change = float(candle.close) - float(previous_close)
        change_percent = change / float(previous_close) * 100 if previous_close else 0.0
        timestamp = pd.Timestamp(candle.opened_at_utc).tz_convert("Europe/Istanbul")
        volume = "—" if pd.isna(candle.volume) else f"{float(candle.volume):,.0f}"
        labels.append(
            f"<b>{symbol}</b><br>"
            f"{timestamp:%d %b %Y · %H:%M} (Istanbul)<br>"
            f"Open {float(candle.open):,.2f}<br>"
            f"High {float(candle.high):,.2f}<br>"
            f"Low {float(candle.low):,.2f}<br>"
            f"Close {float(candle.close):,.2f}<br>"
            f"Change {change:+,.2f} ({change_percent:+.2f}%)<br>"
            f"Volume {volume}"
        )
    return labels


def _focus_chart_on_candles(
    figure: go.Figure,
    candles: pd.DataFrame,
    focus_range: tuple[datetime, datetime] | None,
) -> None:
    if focus_range is not None:
        focused = _candles_inside_focus(candles, focus_range)
        if not focused.empty:
            _apply_visible_range(figure, focused, list(focus_range))
            return

    visible_start = max(0, len(candles) - DEFAULT_VISIBLE_CANDLES)
    visible = candles.iloc[visible_start:]
    _apply_visible_range(
        figure,
        visible,
        [visible.iloc[0]["opened_at_utc"], visible.iloc[-1]["opened_at_utc"]],
    )


def _candles_inside_focus(
    candles: pd.DataFrame,
    focus_range: tuple[datetime, datetime],
) -> pd.DataFrame:
    start = pd.Timestamp(focus_range[0])
    end = pd.Timestamp(focus_range[1])
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    if end.tzinfo is None:
        end = end.tz_localize("UTC")
    if end <= start:
        return candles.iloc[0:0]
    opened_at = pd.to_datetime(candles["opened_at_utc"], utc=True)
    return candles.loc[opened_at.between(start, end)]


def _apply_visible_range(
    figure: go.Figure,
    visible: pd.DataFrame,
    time_range: list,
) -> None:
    lowest = float(visible["low"].min())
    highest = float(visible["high"].max())
    span = max(highest - lowest, highest * 0.01)
    padding = span * 0.06
    figure.update_xaxes(range=time_range, row=1, col=1)
    figure.update_xaxes(range=time_range, row=2, col=1)
    figure.update_yaxes(range=[lowest - padding, highest + padding], row=1, col=1)


def empty_chart(message: str) -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 16, "color": "#7e8999"},
    )
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0b0f17",
        plot_bgcolor="#0b0f17",
        autosize=True,
        height=CHART_HEIGHT,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return figure


CHART_CONFIG = {
    "displaylogo": False,
    "displayModeBar": "hover",
    "scrollZoom": True,
    "responsive": True,
    "doubleClick": "reset",
    "modeBarButtonsToRemove": [
        "select2d",
        "lasso2d",
        "drawline",
        "drawopenpath",
        "drawclosedpath",
        "drawcircle",
        "drawrect",
        "eraseshape",
    ],
}
