from __future__ import annotations

import tomllib
from pathlib import Path


def test_project_exposes_explicit_ui_and_scanner_commands() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]

    assert scripts["trading-vision-ui"] == "trading_vision.ui.app:main"
    assert scripts["trading-vision-worker"] == "trading_vision.worker:main"
    assert scripts["trading-vision-health"] == "trading_vision.health:main"
    assert scripts["trading-vision"] == scripts["trading-vision-ui"]
