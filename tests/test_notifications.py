from trading_vision.models import AlertEvent
from trading_vision.notifications import DeliveryResult, NotificationAdapter


class RecordingAdapter(NotificationAdapter):
    name = "recording"

    def __init__(self) -> None:
        self.events: list[AlertEvent] = []

    def send(self, event: AlertEvent) -> DeliveryResult:
        self.events.append(event)
        return DeliveryResult(succeeded=True)


def test_notification_adapter_can_be_replaced(alert_event) -> None:
    adapter = RecordingAdapter()
    result = adapter.send(alert_event)
    assert result.succeeded
    assert adapter.events == [alert_event]
