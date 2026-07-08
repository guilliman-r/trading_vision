from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from trading_vision.config import Settings
from trading_vision.database import connect
from trading_vision.health import exit_code, main, run_health_checks
from trading_vision.providers.base import FetchResult, MarketDataProvider
from trading_vision.scanner_repository import update_heartbeat


class HealthyProvider(MarketDataProvider):
    name = "healthy fixture"

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        return FetchResult(
            symbol=symbol,
            candles=pd.DataFrame(
                {
                    "opened_at_utc": [pd.Timestamp("2026-07-08T09:00:00Z")],
                    "open": [10.0],
                    "high": [11.0],
                    "low": [9.0],
                    "close": [10.5],
                    "volume": [100.0],
                }
            ),
        )


class BrokenProvider(MarketDataProvider):
    name = "broken fixture"

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        return FetchResult(symbol=symbol, error="provider unavailable")


def test_health_checks_pass_for_valid_database_fresh_scanner_and_provider(database_path) -> None:
    now = datetime(2026, 7, 8, 12, tzinfo=UTC)
    with connect(database_path) as connection:
        update_heartbeat(connection, "idle", 123, now, now)

    checks = run_health_checks(
        Settings(database_path=database_path),
        now=now,
        provider=HealthyProvider(),
    )

    assert exit_code(checks) == 0
    assert [check.status for check in checks] == ["pass", "pass", "pass"]


def test_health_checks_fail_for_stale_scanner_heartbeat(database_path) -> None:
    now = datetime(2026, 7, 8, 12, tzinfo=UTC)
    with connect(database_path) as connection:
        update_heartbeat(
            connection,
            "idle",
            123,
            now - timedelta(hours=1),
            now - timedelta(hours=1),
        )

    checks = run_health_checks(
        Settings(database_path=database_path),
        now=now,
        provider=HealthyProvider(),
        scanner_stale_after=timedelta(minutes=30),
    )

    assert exit_code(checks) == 1
    assert any(check.name == "scanner" and check.status == "fail" for check in checks)


def test_health_checks_fail_for_corrupt_database(tmp_path: Path) -> None:
    database_path = tmp_path / "broken.sqlite3"
    database_path.write_text("not sqlite", encoding="utf-8")

    checks = run_health_checks(
        Settings(database_path=database_path),
        provider=HealthyProvider(),
        check_provider=False,
    )

    assert exit_code(checks) == 1
    assert checks[0].name == "database"
    assert checks[0].status == "fail"


def test_health_checks_fail_for_unavailable_provider(database_path) -> None:
    now = datetime(2026, 7, 8, 12, tzinfo=UTC)
    with connect(database_path) as connection:
        update_heartbeat(connection, "idle", 123, now, now)

    checks = run_health_checks(
        Settings(database_path=database_path),
        now=now,
        provider=BrokenProvider(),
    )

    assert exit_code(checks) == 1
    assert checks[-1].name == "provider"
    assert checks[-1].status == "fail"
    assert "provider unavailable" in checks[-1].message


def test_health_cli_can_skip_provider_check(database_path, capsys) -> None:
    now = datetime.now(UTC)
    with connect(database_path) as connection:
        update_heartbeat(connection, "idle", 123, now, now)

    code = main(
        [
            "--config",
            str(_config_for_database(database_path)),
            "--skip-provider",
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "[PASS] database:" in output
    assert "[PASS] scanner:" in output
    assert "provider" not in output


def _config_for_database(database_path: Path) -> Path:
    config_path = database_path.parent / "config.toml"
    config_path.write_text(f'[storage]\ndatabase_path = "{database_path}"\n', encoding="utf-8")
    return config_path
