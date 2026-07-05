"""Compose filtered scanner rows, diagnostics, and CSV exports."""

from __future__ import annotations

import csv
import sqlite3
import sys
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from io import StringIO
from pathlib import Path

from trading_vision.config import Settings
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
    def __init__(self, connection: sqlite3.Connection, settings: Settings) -> None:
        self.connection = connection
        self.settings = settings

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
        for row in search_pattern_results(self.connection, filters, limit=2_000):
            writer.writerow(_csv_row(row))
        return output.getvalue()

    def _diagnostics(self) -> tuple[tuple[str, str], ...]:
        heartbeat = get_heartbeat(self.connection)
        run = get_latest_scan_run(self.connection)
        database_size = _database_size(self.settings.database_path)
        items = [
            ("Scanner", heartbeat["status"].title() if heartbeat else "Not started"),
            ("Heartbeat", heartbeat["updated_at_utc"] if heartbeat else "—"),
            ("Next wake", heartbeat["next_wake_at_utc"] or "—" if heartbeat else "—"),
            ("Last run", _run_label(run)),
            ("Last success/fail", _run_counts(run)),
            ("Database", str(self.settings.database_path)),
            ("Database size", database_size),
            ("Provider", _provider_health(run)),
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


def _provider_health(run) -> str:
    if run is None:
        return "Yahoo Finance · no scanner run yet"
    return f"{run['provider']} · last run {run['status']}"


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
