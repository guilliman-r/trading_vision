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


def test_optional_container_files_are_present_and_local_only() -> None:
    assert Path("Dockerfile").is_file()
    assert Path("compose.yaml").is_file()
    assert Path(".dockerignore").is_file()

    compose = Path("compose.yaml").read_text(encoding="utf-8")
    assert "127.0.0.1:8050:8050" in compose
    assert "./var:/app/var" in compose
