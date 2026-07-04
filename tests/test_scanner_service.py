from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd

from tests.test_breakouts import resistance_fixture
from trading_vision.config import Settings
from trading_vision.database import connect
from trading_vision.models import Symbol
from trading_vision.providers.base import FetchResult, MarketDataProvider
from trading_vision.repositories import seed_symbols
from trading_vision.scanner_repository import get_heartbeat, get_latest_scan_run
from trading_vision.services.scanner import ScannerService


class PartialProvider(MarketDataProvider):
    name = "scanner fixture"

    def __init__(self) -> None:
        self.requested: list[str] = []

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        self.requested.append(symbol)
        if symbol == "BAD.IS":
            return FetchResult(symbol=symbol, error="deliberate provider failure")
        candles = resistance_fixture()
        candles["is_adjusted"] = True
        candles["source"] = self.name
        candles["fetched_at_utc"] = pd.Timestamp("2026-07-06T17:00:00Z")
        return FetchResult(symbol=symbol, candles=candles)


class CurrentDailyProvider(MarketDataProvider):
    name = "current daily fixture"

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        opened = pd.Timestamp("2026-07-06T00:00:00", tz="Europe/Istanbul").tz_convert("UTC")
        candles = pd.DataFrame(
            {
                "opened_at_utc": [opened],
                "open": [10.0],
                "high": [12.0],
                "low": [9.0],
                "close": [11.0],
                "volume": [100.0],
                "is_complete": [False],
                "is_adjusted": [True],
                "source": [self.name],
                "fetched_at_utc": [pd.Timestamp("2026-07-06T15:30:00Z")],
            }
        )
        return FetchResult(symbol=symbol, candles=candles)


def scanner_settings(database_path, lock_path) -> Settings:
    return Settings(
        database_path=database_path,
        scan_intervals=("1d",),
        scanner_batch_size=1,
        scanner_lookback_bars=500,
        provider_delay_seconds=0,
        scanner_lock_path=lock_path,
    )


def seed_scanner_symbols(database_path) -> None:
    with connect(database_path) as connection:
        seed_symbols(
            connection,
            [
                Symbol("GOOD", "GOOD.IS", is_bist=True),
                Symbol("BAD", "BAD.IS", is_bist=True),
            ],
        )
        connection.commit()


def test_scanner_isolates_symbol_failure_and_persists_diagnostics(database_path, tmp_path) -> None:
    seed_scanner_symbols(database_path)
    provider = PartialProvider()
    service = ScannerService(
        scanner_settings(database_path, tmp_path / "scanner.lock"),
        provider,
        now=lambda: datetime(2026, 7, 6, 17, 30, tzinfo=UTC),
    )
    summary = service.run_once(("GOOD", "BAD"), force=True)
    run = summary.runs[0]
    assert (run.requested, run.succeeded, run.failed) == (2, 1, 1)
    assert run.status == "partial"
    assert run.candles_added == len(resistance_fixture())
    assert provider.requested == ["GOOD.IS", "BAD.IS"]

    with connect(database_path) as connection:
        stored_run = get_latest_scan_run(connection)
        heartbeat = get_heartbeat(connection)
        candles = connection.execute(
            "SELECT COUNT(*) FROM candles WHERE interval = '1d'"
        ).fetchone()[0]
    assert stored_run["status"] == "partial"
    assert "BAD.IS" in json.loads(stored_run["error_summary"])[0]
    assert heartbeat["status"] == "idle"
    assert candles == len(resistance_fixture())


def test_dry_run_caches_candles_without_persisting_patterns(database_path, tmp_path) -> None:
    seed_scanner_symbols(database_path)
    service = ScannerService(
        scanner_settings(database_path, tmp_path / "scanner.lock"),
        PartialProvider(),
        now=lambda: datetime(2026, 7, 6, 17, 30, tzinfo=UTC),
    )
    summary = service.run_once(("GOOD",), force=True, dry_run=True)
    assert summary.runs[0].patterns_added == 0
    with connect(database_path) as connection:
        pattern_count = connection.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
        candle_count = connection.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
    assert pattern_count == 0
    assert candle_count == len(resistance_fixture())


def test_daily_candle_is_complete_after_bist_session_close(database_path, tmp_path) -> None:
    seed_scanner_symbols(database_path)
    service = ScannerService(
        scanner_settings(database_path, tmp_path / "scanner.lock"),
        CurrentDailyProvider(),
        now=lambda: datetime(2026, 7, 6, 15, 30, tzinfo=UTC),
    )
    service.run_once(("GOOD",), force=True)
    with connect(database_path) as connection:
        is_complete = connection.execute(
            """
            SELECT is_complete FROM candles
            WHERE symbol_id = (SELECT id FROM symbols WHERE provider_symbol = 'GOOD.IS')
            """
        ).fetchone()[0]
    assert is_complete == 1
