"""Readable SQL operations used by application services."""

from __future__ import annotations

import csv
import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from trading_vision.models import PatternMatch, Symbol


def upsert_symbol(connection: sqlite3.Connection, symbol: Symbol) -> Symbol:
    connection.execute(
        """
        INSERT INTO symbols (
            display_symbol, provider_symbol, name, exchange, currency,
            is_bist, is_active, source, source_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(provider_symbol) DO UPDATE SET
            display_symbol = excluded.display_symbol,
            name = COALESCE(excluded.name, symbols.name),
            exchange = COALESCE(excluded.exchange, symbols.exchange),
            currency = COALESCE(excluded.currency, symbols.currency),
            is_bist = excluded.is_bist,
            is_active = excluded.is_active,
            source = COALESCE(excluded.source, symbols.source),
            source_date = COALESCE(excluded.source_date, symbols.source_date),
            updated_at_utc = CURRENT_TIMESTAMP
        """,
        (
            symbol.display_symbol,
            symbol.provider_symbol,
            symbol.name,
            symbol.exchange,
            symbol.currency,
            int(symbol.is_bist),
            int(symbol.is_active),
            symbol.source,
            symbol.source_date,
        ),
    )
    row = connection.execute(
        "SELECT * FROM symbols WHERE provider_symbol = ?", (symbol.provider_symbol,)
    ).fetchone()
    return _symbol_from_row(row)


def find_symbol(connection: sqlite3.Connection, query: str) -> Symbol | None:
    normalized = query.strip().upper()
    row = connection.execute(
        """
        SELECT * FROM symbols
        WHERE UPPER(provider_symbol) = ? OR UPPER(display_symbol) = ?
        ORDER BY
            CASE
                WHEN is_bist = 1 AND UPPER(display_symbol) = ? THEN 0
                WHEN UPPER(provider_symbol) = ? THEN 1
                ELSE 2
            END
        LIMIT 1
        """,
        (normalized, normalized, normalized, normalized),
    ).fetchone()
    return _symbol_from_row(row) if row else None


def search_symbols(
    connection: sqlite3.Connection, query: str = "", limit: int = 100
) -> list[Symbol]:
    normalized = f"%{query.strip().upper()}%"
    rows = connection.execute(
        """
        SELECT * FROM symbols
        WHERE is_active = 1
          AND (
              UPPER(display_symbol) LIKE ?
              OR UPPER(provider_symbol) LIKE ?
              OR UPPER(COALESCE(name, '')) LIKE ?
          )
        ORDER BY is_bist DESC, display_symbol
        LIMIT ?
        """,
        (normalized, normalized, normalized, limit),
    ).fetchall()
    return [_symbol_from_row(row) for row in rows]


def import_symbol_catalog(connection: sqlite3.Connection, catalog_path: Path) -> int:
    if not catalog_path.exists():
        return 0
    count = 0
    with catalog_path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            upsert_symbol(
                connection,
                Symbol(
                    display_symbol=row["display_symbol"],
                    provider_symbol=row["provider_symbol"],
                    name=row.get("name") or None,
                    exchange=row.get("exchange") or None,
                    currency=row.get("currency") or None,
                    is_bist=row.get("is_bist", "true").lower() == "true",
                    is_active=row.get("is_active", "true").lower() == "true",
                    source=row.get("source") or None,
                    source_date=row.get("source_date") or None,
                ),
            )
            count += 1
    return count


def upsert_candles(
    connection: sqlite3.Connection,
    symbol_id: int,
    interval: str,
    candles: pd.DataFrame,
) -> int:
    rows: list[tuple[object, ...]] = []
    for candle in candles.itertuples(index=False):
        rows.append(
            (
                symbol_id,
                interval,
                candle.opened_at_utc.isoformat(),
                float(candle.open),
                float(candle.high),
                float(candle.low),
                float(candle.close),
                None if pd.isna(candle.volume) else float(candle.volume),
                int(candle.is_complete),
                int(candle.is_adjusted),
                candle.source,
                candle.fetched_at_utc.isoformat(),
            )
        )
    connection.executemany(
        """
        INSERT INTO candles (
            symbol_id, interval, opened_at_utc, open, high, low, close, volume,
            is_complete, is_adjusted, source, fetched_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol_id, interval, opened_at_utc) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume,
            is_complete = excluded.is_complete,
            is_adjusted = excluded.is_adjusted,
            source = excluded.source,
            fetched_at_utc = excluded.fetched_at_utc
        """,
        rows,
    )
    return len(rows)


def get_candles(
    connection: sqlite3.Connection,
    symbol_id: int,
    interval: str,
    limit: int,
) -> pd.DataFrame:
    rows = connection.execute(
        """
        SELECT opened_at_utc, open, high, low, close, volume,
               is_complete, is_adjusted, source, fetched_at_utc
        FROM candles
        WHERE symbol_id = ? AND interval = ?
        ORDER BY opened_at_utc DESC
        LIMIT ?
        """,
        (symbol_id, interval, limit),
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame([dict(row) for row in reversed(rows)])
    frame["opened_at_utc"] = pd.to_datetime(frame["opened_at_utc"], utc=True)
    frame["fetched_at_utc"] = pd.to_datetime(frame["fetched_at_utc"], utc=True)
    frame["is_complete"] = frame["is_complete"].astype(bool)
    frame["is_adjusted"] = frame["is_adjusted"].astype(bool)
    return frame


def seed_symbols(connection: sqlite3.Connection, symbols: Iterable[Symbol]) -> None:
    for symbol in symbols:
        upsert_symbol(connection, symbol)


def upsert_pattern(
    connection: sqlite3.Connection,
    pattern_id: str,
    symbol_id: int,
    interval: str,
    match: PatternMatch,
) -> bool:
    """Store a current pattern and append a transition only when its state changes."""

    existing = connection.execute(
        "SELECT state FROM patterns WHERE id = ?", (pattern_id,)
    ).fetchone()
    old_state = existing["state"] if existing else None
    points = [
        {
            "label": point.label,
            "index": point.index,
            "occurred_at": point.occurred_at.isoformat(),
            "price": point.price,
        }
        for point in match.points
    ]
    connection.execute(
        """
        INSERT INTO patterns (
            id, symbol_id, interval, pattern_type, direction, state,
            started_at_utc, ended_at_utc, confirmed_at_utc, score,
            boundary_price, target_price, invalidation_price, points_json,
            reasons_json, parameters_json, detector_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            state = excluded.state,
            ended_at_utc = excluded.ended_at_utc,
            confirmed_at_utc = excluded.confirmed_at_utc,
            score = excluded.score,
            boundary_price = excluded.boundary_price,
            target_price = excluded.target_price,
            invalidation_price = excluded.invalidation_price,
            points_json = excluded.points_json,
            reasons_json = excluded.reasons_json,
            parameters_json = excluded.parameters_json,
            detector_version = excluded.detector_version,
            last_seen_at_utc = CURRENT_TIMESTAMP
        """,
        (
            pattern_id,
            symbol_id,
            interval,
            match.pattern_type,
            match.direction,
            match.state,
            match.started_at.isoformat(),
            match.ended_at.isoformat() if match.ended_at else None,
            match.confirmed_at.isoformat() if match.confirmed_at else None,
            match.score,
            match.boundary_price,
            match.target_price,
            match.invalidation_price,
            json.dumps(points, ensure_ascii=False),
            json.dumps(match.reasons, ensure_ascii=False),
            json.dumps(match.parameters, ensure_ascii=False, sort_keys=True),
            match.detector_version,
        ),
    )
    transitioned = old_state != match.state
    if transitioned:
        reason = "Pattern discovered" if old_state is None else f"State changed from {old_state}"
        connection.execute(
            """
            INSERT INTO pattern_transitions(pattern_id, old_state, new_state, reason)
            VALUES (?, ?, ?, ?)
            """,
            (pattern_id, old_state, match.state, reason),
        )
    return transitioned


def get_pattern(connection: sqlite3.Connection, pattern_id: str) -> sqlite3.Row | None:
    return connection.execute("SELECT * FROM patterns WHERE id = ?", (pattern_id,)).fetchone()


def count_pattern_transitions(connection: sqlite3.Connection, pattern_id: str) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM pattern_transitions WHERE pattern_id = ?",
        (pattern_id,),
    ).fetchone()
    return int(row["count"])


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
