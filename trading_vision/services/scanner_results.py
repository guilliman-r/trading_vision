"""Compose filtered scanner rows, diagnostics, and CSV exports."""

from __future__ import annotations

import csv
import sqlite3
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from importlib.metadata import PackageNotFoundError, version
from io import StringIO
from pathlib import Path

from trading_vision import __version__
from trading_vision.config import Settings
from trading_vision.database import schema_version
from trading_vision.scanner_repository import get_heartbeat, get_latest_scan_run
from trading_vision.scanner_results import (
    PatternResultFilters,
    PatternResultRow,
    ScannerResultsSnapshot,
)
from trading_vision.scanner_results_repository import (
    recent_scan_errors,
    recent_scan_warnings,
    search_pattern_results,
)


class ScannerResultsService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        settings: Settings,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.connection = connection
        self.settings = settings
        self.now = now or (lambda: datetime.now(UTC))

    def load(self, filters: PatternResultFilters) -> ScannerResultsSnapshot:
        rows = tuple(search_pattern_results(self.connection, filters))
        return ScannerResultsSnapshot(rows, self._diagnostics())

    def export_csv(self, filters: PatternResultFilters) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            (
                "symbol",
                "interval",
                "pattern_type",
                "direction",
                "state",
                "score",
                "started_at_utc",
                "confirmed_at_utc",
                "boundary",
                "target",
                "invalidation",
                "reasons",
                "app_link",
            )
        )
        for row in search_pattern_results(
            self.connection,
            filters,
            limit=self.settings.scanner_export_limit,
        ):
            writer.writerow(_csv_row(row))
        return output.getvalue()

    def _diagnostics(self) -> tuple[tuple[str, str], ...]:
        heartbeat = get_heartbeat(self.connection)
        run = get_latest_scan_run(self.connection)
        database_size = _database_size(self.settings.database_path)
        items = [
            ("App version", f"Trading Vision {__version__}"),
            ("Schema", schema_version(self.connection)),
            ("Scanner", heartbeat["status"].title() if heartbeat else "Not started"),
            ("Heartbeat", heartbeat["updated_at_utc"] if heartbeat else "—"),
            ("Next wake", heartbeat["next_wake_at_utc"] or "—" if heartbeat else "—"),
            ("Last run", _run_label(run)),
            ("Last success/fail", _run_counts(run)),
            ("Database", str(self.settings.database_path)),
            ("Database size", database_size),
            ("Provider", _provider_health(self.connection, run, self.now())),
            ("Python", sys.version.split()[0]),
            ("Packages", _package_versions()),
        ]
        errors = recent_scan_errors(self.connection)
        warnings = recent_scan_warnings(self.connection)
        items.append(("Recent warnings", " | ".join(warnings) if warnings else "None"))
        items.append(("Recent errors", " | ".join(errors) if errors else "None"))
        return tuple(items)


def _csv_row(row: PatternResultRow) -> tuple[object, ...]:
    return (
        row.provider_symbol,
        row.interval,
        row.pattern_type,
        row.direction,
        row.state,
        row.score,
        row.started_at.isoformat(),
        row.confirmed_at.isoformat() if row.confirmed_at else "",
        row.boundary_price,
        row.target_price if row.target_price is not None else "",
        row.invalidation_price if row.invalidation_price is not None else "",
        " | ".join(row.reasons),
        row.app_link,
    )


def _run_label(run) -> str:
    if run is None:
        return "—"
    duration = ""
    if run["finished_at_utc"]:
        started = datetime.fromisoformat(run["started_at_utc"])
        finished = datetime.fromisoformat(run["finished_at_utc"])
        duration = f" · {(finished - started).total_seconds():.2f}s"
    return f"{run['interval']} · {run['status']}{duration}"


def _run_counts(run) -> str:
    if run is None:
        return "—"
    return f"{run['symbols_succeeded']} / {run['symbols_failed']}"


def _provider_health(connection: sqlite3.Connection, run, now: datetime) -> str:
    latest_bar = _latest_returned_bar_age(connection, now)
    if run is None:
        return f"Yahoo Finance · no scanner run yet · {latest_bar}"
    return (
        f"{run['provider']} · last run {run['status']} · "
        f"{_success_rate(run)} · {_run_latency(run)} · {latest_bar}"
    )


def _success_rate(run) -> str:
    requested = int(run["symbols_requested"])
    if requested <= 0:
        return "success —"
    succeeded = int(run["symbols_succeeded"])
    return f"success {succeeded}/{requested} ({succeeded / requested:.0%})"


def _run_latency(run) -> str:
    if not run["finished_at_utc"]:
        return "latency running"
    started = datetime.fromisoformat(run["started_at_utc"])
    finished = datetime.fromisoformat(run["finished_at_utc"])
    return f"latency {(finished - started).total_seconds():.2f}s"


def _latest_returned_bar_age(connection: sqlite3.Connection, now: datetime) -> str:
    row = connection.execute("SELECT MAX(opened_at_utc) AS opened_at_utc FROM candles").fetchone()
    value = row["opened_at_utc"] if row else None
    if not value:
        return "latest bar —"
    opened_at = _aware_datetime(value)
    return f"latest bar {_age_label(now - opened_at)} old"


def _aware_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _age_label(delta: timedelta) -> str:
    total_seconds = max(0, int(delta.total_seconds()))
    days, remainder = divmod(total_seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes = remainder // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _database_size(path: Path) -> str:
    if not path.exists():
        return "0 B"
    size = path.stat().st_size
    if size < 1_024 * 1_024:
        return f"{size / 1_024:.1f} KiB"
    return f"{size / 1_024 / 1_024:.1f} MiB"


def _package_versions() -> str:
    values = []
    for package in ("dash", "plotly", "pandas", "numpy", "yfinance"):
        try:
            values.append(f"{package} {version(package)}")
        except PackageNotFoundError:
            values.append(f"{package} missing")
    return " · ".join(values)
