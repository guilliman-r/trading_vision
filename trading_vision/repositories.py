"""Readable SQL operations used by application services."""

from __future__ import annotations

import csv
import sqlite3
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from trading_vision.models import Symbol


@dataclass(frozen=True, slots=True)
class CandleUpsertSummary:
    added: int = 0
    updated: int = 0
    unchanged: int = 0

    @property
    def changed(self) -> int:
        return self.added + self.updated


def upsert_symbol(connection: sqlite3.Connection, symbol: Symbol) -> Symbol:
    connection.execute(
        """
        INSERT INTO symbols (
            display_symbol, provider_symbol, name, exchange, currency,
            is_bist, is_active, source, source_date, asset_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(provider_symbol) DO UPDATE SET
            display_symbol = excluded.display_symbol,
            name = COALESCE(excluded.name, symbols.name),
            exchange = COALESCE(excluded.exchange, symbols.exchange),
            currency = COALESCE(excluded.currency, symbols.currency),
            is_bist = excluded.is_bist,
            is_active = excluded.is_active,
            source = COALESCE(excluded.source, symbols.source),
            source_date = COALESCE(excluded.source_date, symbols.source_date),
            asset_type = COALESCE(excluded.asset_type, symbols.asset_type),
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
            symbol.asset_type,
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
    if limit <= 0:
        return []
    rows = connection.execute(
        """
        SELECT * FROM symbols
        WHERE is_active = 1
        ORDER BY is_bist DESC, display_symbol
        """
    ).fetchall()
    symbols = [_symbol_from_row(row) for row in rows]
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        return symbols[:limit]
    matches = [symbol for symbol in symbols if _symbol_matches(symbol, normalized_query)]
    matches.sort(key=lambda symbol: _symbol_search_rank(symbol, normalized_query))
    return matches[:limit]


def list_active_symbols(
    connection: sqlite3.Connection,
    is_bist: bool | None = None,
    limit: int = 1_000,
) -> list[Symbol]:
    if limit <= 0:
        return []
    if is_bist is None:
        rows = connection.execute(
            """
            SELECT * FROM symbols
            WHERE is_active = 1
            ORDER BY is_bist DESC, display_symbol
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT * FROM symbols
            WHERE is_active = 1 AND is_bist = ?
            ORDER BY display_symbol
            LIMIT ?
            """,
            (int(is_bist), limit),
        ).fetchall()
    return [_symbol_from_row(row) for row in rows]


def mark_symbol_inactive(connection: sqlite3.Connection, provider_symbol: str) -> bool:
    cursor = connection.execute(
        """
        UPDATE symbols
        SET is_active = 0, updated_at_utc = CURRENT_TIMESTAMP
        WHERE UPPER(provider_symbol) = UPPER(?)
        """,
        (provider_symbol.strip(),),
    )
    return cursor.rowcount > 0


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
                    asset_type=row.get("asset_type") or None,
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
    return upsert_candles_with_summary(connection, symbol_id, interval, candles).changed


def upsert_candles_with_summary(
    connection: sqlite3.Connection,
    symbol_id: int,
    interval: str,
    candles: pd.DataFrame,
) -> CandleUpsertSummary:
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
    if not rows:
        return CandleUpsertSummary()

    existing = _existing_candle_rows(connection, symbol_id, interval, rows)
    added_rows = []
    updated_rows = []
    unchanged = 0
    for row in rows:
        existing_row = existing.get(row[2])
        if existing_row is None:
            added_rows.append(row)
        elif _candle_row_changed(existing_row, row):
            updated_rows.append(row)
        else:
            unchanged += 1

    _execute_candle_upserts(connection, added_rows + updated_rows)
    return CandleUpsertSummary(
        added=len(added_rows),
        updated=len(updated_rows),
        unchanged=unchanged,
    )


def _execute_candle_upserts(connection: sqlite3.Connection, rows: list[tuple[object, ...]]) -> None:
    if not rows:
        return
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


def _existing_candle_rows(
    connection: sqlite3.Connection,
    symbol_id: int,
    interval: str,
    rows: list[tuple[object, ...]],
) -> dict[str, sqlite3.Row]:
    opened_values = [str(row[2]) for row in rows]
    existing_rows = []
    for opened_chunk in _chunks(opened_values, 500):
        placeholders = ",".join("?" for _ in opened_chunk)
        existing_rows.extend(
            connection.execute(
                f"""
                SELECT opened_at_utc, open, high, low, close, volume,
                       is_complete, is_adjusted, source
                FROM candles
                WHERE symbol_id = ? AND interval = ? AND opened_at_utc IN ({placeholders})
                """,
                (symbol_id, interval, *opened_chunk),
            ).fetchall()
        )
    return {row["opened_at_utc"]: row for row in existing_rows}


def _candle_row_changed(existing: sqlite3.Row, incoming: tuple[object, ...]) -> bool:
    comparable = (
        ("open", incoming[3]),
        ("high", incoming[4]),
        ("low", incoming[5]),
        ("close", incoming[6]),
        ("volume", incoming[7]),
        ("is_complete", incoming[8]),
        ("is_adjusted", incoming[9]),
        ("source", incoming[10]),
    )
    return any(_existing_value_changed(existing[column], value) for column, value in comparable)


def _existing_value_changed(existing: object, incoming: object) -> bool:
    if existing is None or incoming is None:
        return existing is not incoming
    if isinstance(incoming, float | int):
        return float(existing) != float(incoming)
    return existing != incoming


def _chunks(values: list[str], size: int):
    for index in range(0, len(values), size):
        yield values[index : index + size]


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
    return _candles_from_rows(reversed(rows))


def get_candles_between(
    connection: sqlite3.Connection,
    symbol_id: int,
    interval: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    rows = connection.execute(
        """
        SELECT opened_at_utc, open, high, low, close, volume,
               is_complete, is_adjusted, source, fetched_at_utc
        FROM candles
        WHERE symbol_id = ?
          AND interval = ?
          AND datetime(opened_at_utc) >= datetime(?)
          AND datetime(opened_at_utc) <= datetime(?)
        ORDER BY opened_at_utc
        """,
        (symbol_id, interval, start.isoformat(), end.isoformat()),
    ).fetchall()
    return _candles_from_rows(rows)


def get_latest_candle(
    connection: sqlite3.Connection,
    symbol_id: int,
    interval: str,
) -> dict | None:
    rows = connection.execute(
        """
        SELECT opened_at_utc, open, high, low, close, volume,
               is_complete, is_adjusted, source, fetched_at_utc
        FROM candles
        WHERE symbol_id = ? AND interval = ?
        ORDER BY opened_at_utc DESC
        LIMIT 1
        """,
        (symbol_id, interval),
    ).fetchall()
    if not rows:
        return None
    frame = _candles_from_rows(rows)
    return dict(frame.iloc[0])


def _candles_from_rows(rows) -> pd.DataFrame:
    rows = list(rows)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame([dict(row) for row in rows])
    frame["opened_at_utc"] = pd.to_datetime(frame["opened_at_utc"], utc=True)
    frame["fetched_at_utc"] = pd.to_datetime(frame["fetched_at_utc"], utc=True)
    frame["is_complete"] = frame["is_complete"].astype(bool)
    frame["is_adjusted"] = frame["is_adjusted"].astype(bool)
    return frame


def seed_symbols(connection: sqlite3.Connection, symbols: Iterable[Symbol]) -> None:
    for symbol in symbols:
        upsert_symbol(connection, symbol)


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
        asset_type=row["asset_type"],
    )


_TURKISH_SEARCH_TRANSLATION = str.maketrans(
    "ÇĞİÖŞÜçğıöşü",
    "CGIOSUcgiosu",
)


def _normalize_search_text(value: str | None) -> str:
    translated = (value or "").translate(_TURKISH_SEARCH_TRANSLATION)
    decomposed = unicodedata.normalize("NFKD", translated)
    return (
        "".join(character for character in decomposed if not unicodedata.combining(character))
        .casefold()
        .strip()
    )


def _symbol_matches(symbol: Symbol, normalized_query: str) -> bool:
    searchable = " ".join(
        _normalize_search_text(value)
        for value in (symbol.display_symbol, symbol.provider_symbol, symbol.name)
    )
    return normalized_query in searchable


def _symbol_search_rank(symbol: Symbol, normalized_query: str) -> tuple[int, str]:
    display = _normalize_search_text(symbol.display_symbol)
    provider = _normalize_search_text(symbol.provider_symbol)
    name = _normalize_search_text(symbol.name)
    if normalized_query == display:
        priority = 0
    elif normalized_query == provider:
        priority = 1
    elif display.startswith(normalized_query):
        priority = 2
    elif provider.startswith(normalized_query):
        priority = 3
    elif name.startswith(normalized_query):
        priority = 4
    else:
        priority = 5
    return priority, display
