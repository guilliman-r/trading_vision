"""Persistence helpers for user chart drawings."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from trading_vision.models import Drawing


def save_drawing(
    connection: sqlite3.Connection,
    symbol_id: int,
    interval: str,
    drawing_type: str,
    shape: dict[str, Any],
    drawing_id: int | None = None,
) -> Drawing:
    """Insert a new drawing or replace one existing drawing's shape."""

    clean_interval = _required_text(interval, "interval")
    clean_type = _required_text(drawing_type, "drawing type")
    shape_json = json.dumps(shape, sort_keys=True)
    now = datetime.now(UTC).isoformat()

    if drawing_id is None:
        cursor = connection.execute(
            """
            INSERT INTO drawings (
                symbol_id, interval, drawing_type, shape_json, created_at_utc, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (symbol_id, clean_interval, clean_type, shape_json, now, now),
        )
        return _get_drawing(connection, int(cursor.lastrowid))

    cursor = connection.execute(
        """
        UPDATE drawings
        SET interval = ?, drawing_type = ?, shape_json = ?, updated_at_utc = ?
        WHERE id = ? AND symbol_id = ?
        """,
        (clean_interval, clean_type, shape_json, now, drawing_id, symbol_id),
    )
    if cursor.rowcount == 0:
        raise ValueError(f"Unknown drawing id for symbol: {drawing_id}")
    return _get_drawing(connection, drawing_id)


def list_drawings(
    connection: sqlite3.Connection,
    symbol_id: int,
    interval: str,
) -> tuple[Drawing, ...]:
    """Load saved drawings for one symbol and chart interval."""

    rows = connection.execute(
        """
        SELECT *
        FROM drawings
        WHERE symbol_id = ? AND interval = ?
        ORDER BY id
        """,
        (symbol_id, interval),
    ).fetchall()
    return tuple(_drawing_from_row(row) for row in rows)


def delete_drawing(connection: sqlite3.Connection, drawing_id: int) -> bool:
    """Delete one drawing by id and return whether anything changed."""

    cursor = connection.execute("DELETE FROM drawings WHERE id = ?", (drawing_id,))
    return cursor.rowcount > 0


def delete_drawings(
    connection: sqlite3.Connection,
    symbol_id: int,
    interval: str | None = None,
) -> int:
    """Delete all drawings for a symbol, optionally limited to one interval."""

    if interval is None:
        cursor = connection.execute("DELETE FROM drawings WHERE symbol_id = ?", (symbol_id,))
    else:
        cursor = connection.execute(
            "DELETE FROM drawings WHERE symbol_id = ? AND interval = ?",
            (symbol_id, interval),
        )
    return int(cursor.rowcount)


def _get_drawing(connection: sqlite3.Connection, drawing_id: int) -> Drawing:
    row = connection.execute("SELECT * FROM drawings WHERE id = ?", (drawing_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown drawing id: {drawing_id}")
    return _drawing_from_row(row)


def _drawing_from_row(row: sqlite3.Row) -> Drawing:
    return Drawing(
        id=int(row["id"]),
        symbol_id=int(row["symbol_id"]),
        interval=row["interval"],
        drawing_type=row["drawing_type"],
        shape=json.loads(row["shape_json"]),
        created_at=datetime.fromisoformat(row["created_at_utc"]),
        updated_at=datetime.fromisoformat(row["updated_at_utc"]),
    )


def _required_text(value: str, label: str) -> str:
    clean = value.strip()
    if not clean:
        raise ValueError(f"Drawing {label} is required")
    return clean
