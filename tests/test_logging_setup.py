from __future__ import annotations

import logging

from trading_vision.logging_setup import configure_logging, redact_for_log


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


def test_redact_for_log_masks_common_secret_fragments() -> None:
    redacted = redact_for_log(
        "token=abc password:xyz api_key=123 Authorization=Bearer-secret Bearer live-token"
    )

    assert "abc" not in redacted
    assert "xyz" not in redacted
    assert "123" not in redacted
    assert "live-token" not in redacted
    assert "token=<redacted>" in redacted
    assert "password=<redacted>" in redacted
    assert "api_key=<redacted>" in redacted
    assert "Bearer <redacted>" in redacted


def test_configure_logging_redacts_secrets_before_writing(tmp_path) -> None:
    log_path = tmp_path / "trading_vision.log"

    configure_logging("test-process", log_path, "INFO")
    logging.getLogger("trading_vision.test").warning(
        "provider failed with token=%s",
        "super-secret-token",
    )
    for handler in logging.getLogger().handlers:
        handler.flush()

    content = log_path.read_text(encoding="utf-8")
    assert "super-secret-token" not in content
    assert "token=<redacted>" in content
