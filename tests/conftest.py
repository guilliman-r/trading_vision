from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from trading_vision.database import initialize_database
from trading_vision.models import AlertEvent


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.sqlite3"
    initialize_database(path)
    return path


@pytest.fixture
def alert_event() -> AlertEvent:
    now = datetime(2026, 7, 4, 12, tzinfo=UTC)
    return AlertEvent(
        id=1,
        fingerprint="fingerprint",
        pattern_id="pattern",
        provider_symbol="THYAO.IS",
        interval="1d",
        pattern_type="resistance_breakout",
        direction="bullish",
        state="confirmed",
        score=82,
        event_at=now,
        boundary_price=300,
        target_price=330,
        app_link="/?symbol=THYAO.IS",
        created_at=now,
        acknowledged_at=None,
    )
