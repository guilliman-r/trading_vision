"""Render detector output without knowing how the chart data was loaded."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from trading_vision.models import PatternMatch, PatternPoint


def add_pattern_overlays(
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
        _add_boundary_line(figure, candles, pattern, color, opacity, end_time)
        _add_structure(figure, pattern, color, opacity)
        _add_apex_marker(figure, pattern, color, opacity)
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


def _add_structure(
    figure: go.Figure,
    pattern: PatternMatch,
    color: str,
    opacity: float,
) -> None:
    structure = [point for point in pattern.points if point.label not in {"apex", "confirmation"}]
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


def _add_boundary_line(
    figure: go.Figure,
    candles: pd.DataFrame,
    pattern: PatternMatch,
    color: str,
    opacity: float,
    end_time,
) -> None:
    upper_points = [point for point in pattern.points if "upper_touch_" in point.label]
    lower_points = [point for point in pattern.points if "lower_touch_" in point.label]
    if len(upper_points) == 2 and len(lower_points) == 2:
        _add_fitted_boundary(
            figure,
            candles,
            upper_points,
            end_time,
            color,
            opacity,
            f"{pattern.pattern_type} · {pattern.state}",
            "Upper boundary",
        )
        _add_fitted_boundary(
            figure,
            candles,
            lower_points,
            end_time,
            color,
            opacity,
            "Triangle lower boundary",
            "Lower boundary",
        )
        return

    neckline_points = [point for point in pattern.points if "neckline_" in point.label]
    if len(neckline_points) == 2:
        _add_fitted_boundary(
            figure,
            candles,
            neckline_points,
            end_time,
            color,
            opacity,
            f"{pattern.pattern_type} · {pattern.state}",
            "Neckline",
        )
        return

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
                f"State: {pattern.state}<br>Boundary: %{{y:,.2f}}"
                "<extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )


def _add_fitted_boundary(
    figure: go.Figure,
    candles: pd.DataFrame,
    points: list[PatternPoint],
    end_time,
    color: str,
    opacity: float,
    name: str,
    label: str,
) -> None:
    first, second = points
    slope = (second.price - first.price) / (second.index - first.index)
    eligible = candles.loc[candles["opened_at_utc"] <= pd.Timestamp(end_time)]
    end_index = len(eligible) - 1
    end_price = second.price + slope * (end_index - second.index)
    figure.add_trace(
        go.Scatter(
            x=[first.occurred_at, end_time],
            y=[first.price, end_price],
            mode="lines",
            line={"color": color, "width": 2},
            opacity=opacity,
            name=name,
            hovertemplate=f"{label}: %{{y:,.2f}}<extra></extra>",
        ),
        row=1,
        col=1,
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


def _add_apex_marker(
    figure: go.Figure,
    pattern: PatternMatch,
    color: str,
    opacity: float,
) -> None:
    apex = next((point for point in pattern.points if point.label == "apex"), None)
    if apex is None:
        return
    figure.add_trace(
        go.Scatter(
            x=[apex.occurred_at],
            y=[apex.price],
            mode="markers",
            marker={"color": color, "size": 9, "symbol": "x"},
            opacity=opacity,
            name="Apex",
            hovertemplate="Projected apex<br>%{x}<br>%{y:,.2f}<extra></extra>",
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
