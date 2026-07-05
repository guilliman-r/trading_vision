"""SQLite operations used only by the background scanner."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import pandas as pd

from trading_vision.models import Symbol


def list_active_bist_symbols(connection: sqlite3.Connection) -> list[Symbol]:
    rows = connection.execute(
        """
        SELECT * FROM symbols
        WHERE is_bist = 1 AND is_active = 1
        ORDER BY provider_symbol
        """
    ).fetchall()
    return [_symbol_from_row(row) for row in rows]


def latest_completed_candle_at(
    connection: sqlite3.Connection,
    symbol_id: int,
    interval: str,
) -> datetime | None:
    row = connection.execute(
        """
        SELECT MAX(opened_at_utc) AS opened_at_utc
        FROM candles
        WHERE symbol_id = ? AND interval = ? AND is_complete = 1
        """,
        (symbol_id, interval),
    ).fetchone()
    value = row["opened_at_utc"]
    return pd.Timestamp(value).to_pydatetime() if value else None


def count_candles(connection: sqlite3.Connection, symbol_id: int, interval: str) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM candles WHERE symbol_id = ? AND interval = ?",
        (symbol_id, interval),
    ).fetchone()
    return int(row["count"])


def start_scan_run(
    connection: sqlite3.Connection,
    started_at: datetime,
    interval: str,
    provider: str,
    requested: int,
    dry_run: bool,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO scan_runs (
            started_at_utc, interval, provider, symbols_requested, dry_run, status
        ) VALUES (?, ?, ?, ?, ?, 'running')
        """,
        (started_at.isoformat(), interval, provider, requested, int(dry_run)),
    )
    return int(cursor.lastrowid)


def finish_scan_run(
    connection: sqlite3.Connection,
    run_id: int,
    finished_at: datetime,
    succeeded: int,
    failed: int,
    candles_added: int,
    patterns_added: int,
    status: str,
    errors: list[str],
    warnings: list[str] | None = None,
) -> None:
    concise_errors = [error[:300] for error in errors[:20]]
    concise_warnings = [warning[:300] for warning in (warnings or [])[:20]]
    connection.execute(
        """
        UPDATE scan_runs SET
            finished_at_utc = ?, symbols_succeeded = ?, symbols_failed = ?,
            candles_added = ?, patterns_added = ?, status = ?,
            error_summary = ?, warning_summary = ?
        WHERE id = ?
        """,
        (
            finished_at.isoformat(),
            succeeded,
            failed,
            candles_added,
            patterns_added,
            status,
            json.dumps(concise_errors, ensure_ascii=False) if concise_errors else None,
            json.dumps(concise_warnings, ensure_ascii=False) if concise_warnings else None,
            run_id,
        ),
    )


def update_heartbeat(
    connection: sqlite3.Connection,
    status: str,
    process_id: int,
    started_at: datetime,
    updated_at: datetime,
    next_wake_at: datetime | None = None,
    last_run_id: int | None = None,
    message: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO scanner_heartbeat (
            id, status, process_id, started_at_utc, updated_at_utc,
            next_wake_at_utc, last_run_id, message
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            status = excluded.status,
            process_id = excluded.process_id,
            started_at_utc = excluded.started_at_utc,
            updated_at_utc = excluded.updated_at_utc,
            next_wake_at_utc = excluded.next_wake_at_utc,
            last_run_id = COALESCE(excluded.last_run_id, scanner_heartbeat.last_run_id),
            message = excluded.message
        """,
        (
            status,
            process_id,
            started_at.isoformat(),
            updated_at.isoformat(),
            next_wake_at.isoformat() if next_wake_at else None,
            last_run_id,
            message,
        ),
    )


def get_latest_scan_run(connection: sqlite3.Connection) -> sqlite3.Row | None:
    return connection.execute("SELECT * FROM scan_runs ORDER BY id DESC LIMIT 1").fetchone()


def get_heartbeat(connection: sqlite3.Connection) -> sqlite3.Row | None:
    return connection.execute("SELECT * FROM scanner_heartbeat WHERE id = 1").fetchone()


def _symbol_from_row(row: sqlite3.Row) -> Symbol:
    return Symbol(
        id=row["id"],
        display_symbol=row["display_symbol"],
        provider_symbol=row["provider_symbol"],
        name=row["name"],
        exchange=row["exchange"],
        currency=row["currency"],
        is_bist=bool(row["is_bist"]),
        is_active=bool(row["is_active"]),
        source=row["source"],
        source_date=row["source_date"],
    )
