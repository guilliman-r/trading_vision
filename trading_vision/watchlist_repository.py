"""Plain SQLite operations for watchlists and ordered watchlist items."""

from __future__ import annotations

import json
import sqlite3

from trading_vision.config import SUPPORTED_SCAN_INTERVALS
from trading_vision.models import Symbol, Watchlist, WatchlistItem


def create_watchlist(
    connection: sqlite3.Connection,
    name: str,
    description: str | None = None,
) -> Watchlist:
    clean_name = _clean_name(name)
    connection.execute(
        """
        INSERT INTO watchlists(name, description)
        VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET
            description = COALESCE(excluded.description, watchlists.description),
            updated_at_utc = CURRENT_TIMESTAMP
        """,
        (clean_name, description),
    )
    row = connection.execute("SELECT * FROM watchlists WHERE name = ?", (clean_name,)).fetchone()
    return _watchlist_from_row(row)


def list_watchlists(connection: sqlite3.Connection) -> tuple[Watchlist, ...]:
    rows = connection.execute("SELECT * FROM watchlists ORDER BY name").fetchall()
    return tuple(_watchlist_from_row(row) for row in rows)


def add_watchlist_item(
    connection: sqlite3.Connection,
    watchlist_id: int,
    symbol_id: int,
    scan_intervals: tuple[str, ...] = (),
) -> WatchlistItem:
    _require_watchlist(connection, watchlist_id)
    _validate_scan_intervals(scan_intervals)
    position = _next_position(connection, watchlist_id)
    connection.execute(
        """
        INSERT INTO watchlist_items(watchlist_id, symbol_id, position, scan_intervals_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(watchlist_id, symbol_id) DO UPDATE SET
            scan_intervals_json = excluded.scan_intervals_json,
            updated_at_utc = CURRENT_TIMESTAMP
        """,
        (watchlist_id, symbol_id, position, json.dumps(scan_intervals)),
    )
    return _watchlist_item(connection, watchlist_id, symbol_id)


def list_watchlist_items(
    connection: sqlite3.Connection,
    watchlist_id: int,
) -> tuple[WatchlistItem, ...]:
    _require_watchlist(connection, watchlist_id)
    rows = connection.execute(
        """
        SELECT wi.*, s.*
        FROM watchlist_items AS wi
        JOIN symbols AS s ON s.id = wi.symbol_id
        WHERE wi.watchlist_id = ?
        ORDER BY wi.position
        """,
        (watchlist_id,),
    ).fetchall()
    return tuple(_item_from_row(row) for row in rows)


def reorder_watchlist_item(
    connection: sqlite3.Connection,
    watchlist_id: int,
    symbol_id: int,
    new_position: int,
) -> tuple[WatchlistItem, ...]:
    items = list(list_watchlist_items(connection, watchlist_id))
    if not items:
        return ()
    moving = next((item for item in items if item.symbol.id == symbol_id), None)
    if moving is None:
        raise ValueError("Symbol is not in this watchlist")
    items.remove(moving)
    bounded_position = max(1, min(new_position, len(items) + 1))
    items.insert(bounded_position - 1, moving)
    _rewrite_positions(connection, watchlist_id, items)
    return list_watchlist_items(connection, watchlist_id)


def remove_watchlist_item(
    connection: sqlite3.Connection,
    watchlist_id: int,
    symbol_id: int,
) -> bool:
    cursor = connection.execute(
        "DELETE FROM watchlist_items WHERE watchlist_id = ? AND symbol_id = ?",
        (watchlist_id, symbol_id),
    )
    _compact_positions(connection, watchlist_id)
    return cursor.rowcount > 0


def _watchlist_item(
    connection: sqlite3.Connection,
    watchlist_id: int,
    symbol_id: int,
) -> WatchlistItem:
    row = connection.execute(
        """
        SELECT wi.*, s.*
        FROM watchlist_items AS wi
        JOIN symbols AS s ON s.id = wi.symbol_id
        WHERE wi.watchlist_id = ? AND wi.symbol_id = ?
        """,
        (watchlist_id, symbol_id),
    ).fetchone()
    if row is None:
        raise ValueError("Symbol is not in this watchlist")
    return _item_from_row(row)


def _rewrite_positions(
    connection: sqlite3.Connection,
    watchlist_id: int,
    items: list[WatchlistItem],
) -> None:
    temporary_offset = len(items) + 1_000
    for index, item in enumerate(items, start=1):
        connection.execute(
            """
            UPDATE watchlist_items
            SET position = ?
            WHERE watchlist_id = ? AND symbol_id = ?
            """,
            (temporary_offset + index, watchlist_id, item.symbol.id),
        )
    for index, item in enumerate(items, start=1):
        connection.execute(
            """
            UPDATE watchlist_items
            SET position = ?, updated_at_utc = CURRENT_TIMESTAMP
            WHERE watchlist_id = ? AND symbol_id = ?
            """,
            (index, watchlist_id, item.symbol.id),
        )


def _compact_positions(connection: sqlite3.Connection, watchlist_id: int) -> None:
    items = list(list_watchlist_items(connection, watchlist_id))
    _rewrite_positions(connection, watchlist_id, items)


def _next_position(connection: sqlite3.Connection, watchlist_id: int) -> int:
    row = connection.execute(
        """
        SELECT COALESCE(MAX(position), 0) + 1 AS position
        FROM watchlist_items
        WHERE watchlist_id = ?
        """,
        (watchlist_id,),
    ).fetchone()
    return int(row["position"])


def _require_watchlist(connection: sqlite3.Connection, watchlist_id: int) -> None:
    row = connection.execute("SELECT 1 FROM watchlists WHERE id = ?", (watchlist_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown watchlist id: {watchlist_id}")


def _validate_scan_intervals(intervals: tuple[str, ...]) -> None:
    invalid = set(intervals).difference(SUPPORTED_SCAN_INTERVALS)
    if invalid:
        allowed = ", ".join(SUPPORTED_SCAN_INTERVALS)
        invalid_values = ", ".join(sorted(invalid))
        raise ValueError(f"Unsupported watchlist scan intervals: {invalid_values}; use {allowed}")


def _clean_name(name: str) -> str:
    clean = name.strip()
    if not clean:
        raise ValueError("Watchlist name is required")
    return clean


def _watchlist_from_row(row: sqlite3.Row) -> Watchlist:
    return Watchlist(id=int(row["id"]), name=row["name"], description=row["description"])


def _item_from_row(row: sqlite3.Row) -> WatchlistItem:
    symbol = Symbol(
        id=row["symbol_id"],
        display_symbol=row["display_symbol"],
        provider_symbol=row["provider_symbol"],
        name=row["name"],
        exchange=row["exchange"],
        currency=row["currency"],
        is_bist=bool(row["is_bist"]),
        is_active=bool(row["is_active"]),
        source=row["source"],
        source_date=row["source_date"],
        asset_type=row["asset_type"],
    )
    return WatchlistItem(
        watchlist_id=int(row["watchlist_id"]),
        symbol=symbol,
        position=int(row["position"]),
        scan_intervals=tuple(json.loads(row["scan_intervals_json"])),
    )
