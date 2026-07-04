"""Small Dash components for the in-app notification center."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from dash import dcc, html

from trading_vision.models import AlertEvent
from trading_vision.ui import ids


def render_alerts(events: tuple[AlertEvent, ...]) -> list:
    if not events:
        return [html.P("No pattern alerts yet.", className="alert-empty")]
    return [_alert_card(event) for event in events]


def _alert_card(event: AlertEvent) -> html.Div:
    acknowledged = event.acknowledged_at is not None
    target = f"Target {event.target_price:,.2f}" if event.target_price is not None else "No target"
    event_time = event.event_at.astimezone(ZoneInfo("Europe/Istanbul")).strftime("%d %b · %H:%M")
    return html.Div(
        [
            html.Div(
                [
                    html.Strong(event.pattern_type.replace("_", " ").title()),
                    html.Span("Read" if acknowledged else "New"),
                ],
                className="alert-card-heading",
            ),
            html.P(
                f"{event.provider_symbol} · {event.interval.upper()} · "
                f"{event.direction} · {event.state} · {event_time}"
            ),
            html.Div(
                [
                    html.Span(f"Score {event.score:.0f}"),
                    html.Span(f"Level {event.boundary_price:,.2f}"),
                    html.Span(target),
                ],
                className="alert-metrics",
            ),
            html.Div(
                [
                    dcc.Link("Open chart", href=event.app_link, className="alert-link"),
                    html.Button(
                        "Acknowledge",
                        id={"type": ids.ALERT_ACK_TYPE, "alert_id": event.id},
                        disabled=acknowledged,
                        className="alert-action",
                    ),
                    html.Button(
                        "Mute pattern",
                        id={"type": ids.ALERT_MUTE_TYPE, "alert_id": event.id},
                        className="alert-action muted",
                    ),
                ],
                className="alert-actions",
            ),
        ],
        className="alert-card acknowledged" if acknowledged else "alert-card unread",
    )
