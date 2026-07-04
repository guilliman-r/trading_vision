"""Pure Plotly figure construction with no network or database calls."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from trading_vision.models import PatternMatch
from trading_vision.ui.pattern_overlays import add_pattern_overlays


def build_chart(
    candles: pd.DataFrame,
    symbol: str,
    interval: str,
    patterns: tuple[PatternMatch, ...] = (),
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
        margin={"l": 14, "r": 58, "t": 12, "b": 28},
        showlegend=False,
        hovermode="x unified",
        dragmode="pan",
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
    figure.update_yaxes(
        showgrid=True,
        gridcolor="#18202d",
        zeroline=False,
        side="right",
        fixedrange=False,
    )
    return figure


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
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return figure


CHART_CONFIG = {
    "displaylogo": False,
    "scrollZoom": True,
    "responsive": True,
    "modeBarButtonsToAdd": ["drawline", "drawrect", "drawcircle", "eraseshape"],
}
