"""Replaceable contract for future external notification channels."""

from __future__ import annotations

from dataclasses import dataclass

from trading_vision.models import AlertEvent


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    succeeded: bool
    error: str | None = None


class NotificationAdapter:
    """Base class implemented by future Telegram, email, or desktop channels."""

    name = "unknown"

    def send(self, event: AlertEvent) -> DeliveryResult:
        raise NotImplementedError
