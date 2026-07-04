from trading_vision.ui.scanner_status import scanner_status_text


def test_missing_scanner_heartbeat_has_clear_label() -> None:
    assert scanner_status_text(None) == "Scanner not started"
