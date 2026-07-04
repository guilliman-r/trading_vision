from __future__ import annotations

from pathlib import Path

import pytest

from trading_vision.database import initialize_database


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.sqlite3"
    initialize_database(path)
    return path
