"""Small command-line health checks for local Trading Vision deployments."""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from trading_vision.config import Settings, load_settings
from trading_vision.database import connect, database_integrity_result, schema_version
from trading_vision.providers.base import MarketDataProvider
from trading_vision.providers.yahoo import YahooFinanceProvider
from trading_vision.scanner_repository import get_heartbeat

REQUIRED_TABLES = {
    "alert_events",
    "alert_rules",
    "candles",
    "pattern_mutes",
    "patterns",
    "scan_runs",
    "scanner_heartbeat",
    "schema_migrations",
    "symbols",
}


@dataclass(frozen=True, slots=True)
class HealthCheck:
    name: str
    status: str
    message: str

    @property
    def failed(self) -> bool:
        return self.status == "fail"


def run_health_checks(
    settings: Settings,
    *,
    now: datetime | None = None,
    provider: MarketDataProvider | None = None,
    check_provider: bool = True,
    scanner_stale_after: timedelta = timedelta(minutes=30),
) -> list[HealthCheck]:
    checked_at = now or datetime.now(UTC)
    checks = [_check_database(settings.database_path)]
    if not checks[0].failed:
        checks.append(_check_scanner(settings.database_path, checked_at, scanner_stale_after))
    if check_provider:
        checks.append(_check_provider(settings, provider or YahooFinanceProvider(max_attempts=1)))
    return checks


def exit_code(checks: list[HealthCheck]) -> int:
    return 1 if any(check.failed for check in checks) else 0


def _check_database(database_path: Path) -> HealthCheck:
    if not database_path.exists():
        return HealthCheck("database", "fail", f"Database file does not exist: {database_path}")
    try:
        with connect(database_path) as connection:
            quick_check = database_integrity_result(connection)
            if quick_check != "ok":
                return HealthCheck("database", "fail", f"SQLite quick_check failed: {quick_check}")
            missing = REQUIRED_TABLES.difference(_table_names(connection))
            if missing:
                missing_tables = ", ".join(sorted(missing))
                return HealthCheck("database", "fail", f"Missing tables: {missing_tables}")
            return HealthCheck("database", "pass", schema_version(connection))
    except sqlite3.DatabaseError as error:
        return HealthCheck("database", "fail", f"SQLite error: {error}")


def _check_scanner(
    database_path: Path,
    now: datetime,
    scanner_stale_after: timedelta,
) -> HealthCheck:
    try:
        with connect(database_path) as connection:
            heartbeat = get_heartbeat(connection)
    except sqlite3.DatabaseError as error:
        return HealthCheck("scanner", "fail", f"SQLite error: {error}")
    if heartbeat is None:
        return HealthCheck("scanner", "fail", "Scanner heartbeat is missing")

    status = str(heartbeat["status"])
    updated_at = pd.Timestamp(heartbeat["updated_at_utc"]).to_pydatetime()
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    age = now - updated_at.astimezone(UTC)
    if status == "stopped":
        return HealthCheck("scanner", "fail", "Scanner heartbeat says stopped")
    if age > scanner_stale_after:
        minutes = int(age.total_seconds() // 60)
        return HealthCheck("scanner", "fail", f"Scanner heartbeat is stale: {minutes} minutes old")
    return HealthCheck("scanner", "pass", f"{status}; updated {updated_at.isoformat()}")


def _check_provider(settings: Settings, provider: MarketDataProvider) -> HealthCheck:
    try:
        result = provider.fetch_history(settings.default_symbol, settings.default_interval)
    except Exception as error:
        return HealthCheck("provider", "fail", f"{provider.name} raised: {error}")
    if not result.succeeded:
        return HealthCheck("provider", "fail", result.error or "Provider returned no candles")
    message = f"{provider.name} returned {len(result.candles)} candles"
    return HealthCheck("provider", "pass", message)


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()
    return {str(row["name"]) for row in rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check local Trading Vision health")
    parser.add_argument("--config", type=Path, help="Optional config.toml path")
    parser.add_argument(
        "--scanner-stale-minutes",
        type=int,
        default=30,
        help="Fail when the scanner heartbeat is older than this many minutes",
    )
    parser.add_argument(
        "--skip-provider",
        action="store_true",
        help="Skip the live provider request and check only local database/scanner state",
    )
    arguments = parser.parse_args(argv)

    settings = load_settings(arguments.config)
    checks = run_health_checks(
        settings,
        check_provider=not arguments.skip_provider,
        scanner_stale_after=timedelta(minutes=arguments.scanner_stale_minutes),
    )
    for check in checks:
        print(f"[{check.status.upper()}] {check.name}: {check.message}")
    return exit_code(checks)


if __name__ == "__main__":
    raise SystemExit(main())
