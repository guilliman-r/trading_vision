"""Small helpers for safe, readable user-visible text."""

from __future__ import annotations

import re

CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
WHITESPACE = re.compile(r"\s+")


def safe_display_text(value: object, fallback: str = "—", max_length: int = 160) -> str:
    """Strip control characters, collapse whitespace, and cap display length."""

    text = CONTROL_CHARACTERS.sub("", str(value or ""))
    text = WHITESPACE.sub(" ", text).strip()
    if not text:
        return fallback
    if len(text) <= max_length:
        return text
    return f"{text[: max(1, max_length - 1)].rstrip()}…"
