"""Pure Plotly figure construction with no network or database calls."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from trading_vision.models import PatternMatch


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
    _add_pattern_overlays(figure, candles, patterns)
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


def _add_pattern_overlays(
    figure: go.Figure,
    candles: pd.DataFrame,
    patterns: tuple[PatternMatch, ...],
) -> None:
    last_time = candles.iloc[-1]["opened_at_utc"]
    for pattern in patterns:
        if pattern.state == "expired":
            continue
        color = _pattern_color(pattern)
        opacity = 0.45 if pattern.state == "invalidated" else 0.9
        end_time = pattern.ended_at or last_time
        figure.add_trace(
            go.Scatter(
                x=[pattern.started_at, end_time],
                y=[pattern.boundary_price, pattern.boundary_price],
                mode="lines",
                line={"color": color, "width": 2},
                opacity=opacity,
                name=f"{pattern.pattern_type} · {pattern.state}",
                hovertemplate=(
                    f"{pattern.pattern_type.replace('_', ' ').title()}<br>"
                    f"State: {pattern.state}<br>Level: {pattern.boundary_price:,.2f}"
                    "<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )
        structure = [point for point in pattern.points if point.label != "confirmation"]
        figure.add_trace(
            go.Scatter(
                x=[point.occurred_at for point in structure],
                y=[point.price for point in structure],
                text=[point.label.replace("_", " ").title() for point in structure],
                mode="lines+markers",
                line={"color": color, "width": 1, "dash": "dot"},
                marker={"color": color, "size": 9, "symbol": "circle-open", "line_width": 2},
                opacity=opacity,
                name="Pattern structure",
                hovertemplate="%{text}<br>%{x}<br>%{y:,.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        _add_confirmation_marker(figure, pattern, color)
        _add_reference_line(figure, pattern, "target_price", "Target", color, "dot", last_time)
        _add_reference_line(
            figure,
            pattern,
            "invalidation_price",
            "Invalidation",
            "#8b96a8",
            "dash",
            last_time,
        )


def _add_confirmation_marker(
    figure: go.Figure,
    pattern: PatternMatch,
    color: str,
) -> None:
    confirmation = next(
        (point for point in pattern.points if point.label == "confirmation"),
        None,
    )
    if confirmation is None:
        return
    symbol = "triangle-up" if pattern.direction == "bullish" else "triangle-down"
    figure.add_trace(
        go.Scatter(
            x=[confirmation.occurred_at],
            y=[confirmation.price],
            mode="markers",
            marker={"color": color, "size": 13, "symbol": symbol},
            name="Confirmation",
            hovertemplate="Confirmation<br>%{x}<br>%{y:,.2f}<extra></extra>",
        ),
        row=1,
        col=1,
    )


def _add_reference_line(
    figure: go.Figure,
    pattern: PatternMatch,
    field: str,
    label: str,
    color: str,
    dash: str,
    last_time,
) -> None:
    price = getattr(pattern, field)
    if price is None:
        return
    figure.add_trace(
        go.Scatter(
            x=[pattern.started_at, last_time],
            y=[price, price],
            mode="lines",
            line={"color": color, "width": 1, "dash": dash},
            opacity=0.65,
            name=label,
            hovertemplate=f"{label}: %{{y:,.2f}}<extra></extra>",
        ),
        row=1,
        col=1,
    )


def _pattern_color(pattern: PatternMatch) -> str:
    if pattern.state == "invalidated":
        return "#8b96a8"
    if pattern.state == "forming":
        return "#4da3ff"
    return "#19c37d" if pattern.direction == "bullish" else "#f05a67"


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
