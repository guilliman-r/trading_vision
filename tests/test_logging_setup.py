from __future__ import annotations

import logging

from trading_vision.logging_setup import configure_logging


def test_configure_logging_writes_process_label_to_rotating_file(tmp_path) -> None:
    log_path = tmp_path / "trading_vision.log"

    configure_logging("test-process", log_path, "INFO")
    logging.getLogger("trading_vision.test").info("hello logging")
    for handler in logging.getLogger().handlers:
        handler.flush()

    content = log_path.read_text(encoding="utf-8")
    assert "test-process" in content
    assert "trading_vision.test" in content
    assert "hello logging" in content
