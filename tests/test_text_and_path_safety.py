from __future__ import annotations

import pytest

from trading_vision.path_safety import require_path_inside
from trading_vision.text_safety import safe_display_text


def test_safe_display_text_strips_controls_collapses_space_and_caps_length() -> None:
    value = "  THYAO\x00\n\tVery   Long Name  "

    assert safe_display_text(value, max_length=16) == "THYAO Very Long…"


def test_safe_display_text_uses_fallback_for_empty_values() -> None:
    assert safe_display_text("\x00\n", fallback="Yahoo instrument") == "Yahoo instrument"


def test_require_path_inside_accepts_project_child(tmp_path) -> None:
    child = tmp_path / "data" / "catalog.csv"

    assert require_path_inside(tmp_path, child) == child.resolve()


def test_require_path_inside_rejects_parent_escape(tmp_path) -> None:
    with pytest.raises(ValueError, match="Path must stay inside"):
        require_path_inside(tmp_path / "project", tmp_path / "catalog.csv")
