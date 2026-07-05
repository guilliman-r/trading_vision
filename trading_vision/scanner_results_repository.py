"""Filtered scanner result queries kept out of UI callbacks."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from trading_vision.scanner_results import PatternResultFilters, PatternResultRow


def search_pattern_results(
    connection: sqlite3.Connection,
    filters: PatternResultFilters,
    limit: int = 500,
) -> list[PatternResultRow]:
    cutoff = datetime.now(UTC) - timedelta(days=max(0, filters.lookback_days))
    parameters = {
        "minimum_score": filters.minimum_score,
        "symbol": f"%{filters.symbol.strip().upper()}%",
        "interval": filters.interval,
        "pattern_type": filters.pattern_type,
        "direction": filters.direction,
        "state": filters.state,
        "lookback_days": filters.lookback_days,
        "cutoff": cutoff.isoformat(),
        "limit": max(1, min(limit, 2_000)),
    }
    rows = connection.execute(
        """
        SELECT p.*, s.provider_symbol
        FROM patterns AS p
        JOIN symbols AS s ON s.id = p.symbol_id
        WHERE p.score >= :minimum_score
          AND (:symbol = '%%' OR UPPER(s.provider_symbol) LIKE :symbol)
          AND (:interval = '' OR p.interval = :interval)
          AND (:pattern_type = '' OR p.pattern_type = :pattern_type)
          AND (:direction = '' OR p.direction = :direction)
          AND (:state = '' OR p.state = :state)
          AND (
              :lookback_days <= 0
              OR datetime(p.last_seen_at_utc) >= datetime(:cutoff)
          )
        ORDER BY COALESCE(p.confirmed_at_utc, p.last_seen_at_utc) DESC, p.score DESC
        LIMIT :limit
        """,
        parameters,
    ).fetchall()
    return [_result_from_row(row) for row in rows]


def recent_scan_errors(connection: sqlite3.Connection, limit: int = 3) -> list[str]:
    rows = connection.execute(
        """
        SELECT error_summary FROM scan_runs
        WHERE error_summary IS NOT NULL
        ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    errors: list[str] = []
    for row in rows:
        errors.extend(json.loads(row["error_summary"]))
    return errors[:limit]


def recent_scan_warnings(connection: sqlite3.Connection, limit: int = 3) -> list[str]:
    rows = connection.execute(
        """
        SELECT warning_summary FROM scan_runs
        WHERE warning_summary IS NOT NULL
        ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    warnings: list[str] = []
    for row in rows:
        warnings.extend(json.loads(row["warning_summary"]))
    return warnings[:limit]


def _result_from_row(row: sqlite3.Row) -> PatternResultRow:
    provider_symbol = row["provider_symbol"]
    interval = row["interval"]
    pattern_id = row["id"]
    return PatternResultRow(
        pattern_id=pattern_id,
        provider_symbol=provider_symbol,
        interval=interval,
        pattern_type=row["pattern_type"],
        direction=row["direction"],
        state=row["state"],
        score=float(row["score"]),
        started_at=datetime.fromisoformat(row["started_at_utc"]),
        confirmed_at=(
            datetime.fromisoformat(row["confirmed_at_utc"]) if row["confirmed_at_utc"] else None
        ),
        last_seen_at=_database_time(row["last_seen_at_utc"]),
        boundary_price=float(row["boundary_price"]),
        target_price=float(row["target_price"]) if row["target_price"] is not None else None,
        invalidation_price=(
            float(row["invalidation_price"]) if row["invalidation_price"] is not None else None
        ),
        reasons=tuple(json.loads(row["reasons_json"])),
        app_link=f"/?symbol={provider_symbol}&interval={interval}&pattern={pattern_id}",
    )


def _database_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace(" ", "T"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
