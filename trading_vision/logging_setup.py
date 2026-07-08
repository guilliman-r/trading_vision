"""Small logging setup shared by the UI and scanner processes."""

from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

SENSITIVE_PATTERNS = (
    re.compile(r"(?i)\b(token|secret|password|api[_-]?key|authorization)\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"),
)


def configure_logging(process_name: str, log_path: Path, level: str = "INFO") -> None:
    """Configure console and rotating-file logging with a visible process label."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level.upper())

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(tv_process)s %(name)s %(message)s")
    process_filter = _ProcessFilter(process_name)
    redaction_filter = _RedactionFilter()

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    console.addFilter(process_filter)
    console.addFilter(redaction_filter)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(process_filter)
    file_handler.addFilter(redaction_filter)

    root.addHandler(console)
    root.addHandler(file_handler)


def redact_for_log(value: object) -> str:
    """Return a string with common secret-looking fragments redacted."""

    text = str(value)
    text = SENSITIVE_PATTERNS[0].sub(lambda match: f"{match.group(1)}=<redacted>", text)
    return SENSITIVE_PATTERNS[1].sub("Bearer <redacted>", text)


class _ProcessFilter(logging.Filter):
    def __init__(self, process_name: str) -> None:
        super().__init__()
        self.process_name = process_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.tv_process = self.process_name
        return True


class _RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_for_log(record.getMessage())
        record.args = ()
        return True
