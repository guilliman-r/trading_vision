"""Pattern and immutable state-transition persistence."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from trading_vision.models import PatternMatch, PatternTransition


def upsert_pattern(
    connection: sqlite3.Connection,
    pattern_id: str,
    symbol_id: int,
    interval: str,
    match: PatternMatch,
) -> PatternTransition | None:
    """Store current state and return only a newly appended transition."""

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
    if old_state == match.state:
        return None

    changed_at = datetime.now(UTC)
    reason = "Pattern discovered" if old_state is None else f"State changed from {old_state}"
    cursor = connection.execute(
        """
        INSERT INTO pattern_transitions(
            pattern_id, old_state, new_state, changed_at_utc, reason
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (pattern_id, old_state, match.state, changed_at.isoformat(), reason),
    )
    return PatternTransition(
        id=int(cursor.lastrowid),
        pattern_id=pattern_id,
        old_state=old_state,
        new_state=match.state,
        changed_at=changed_at,
        reason=reason,
    )


def get_pattern(connection: sqlite3.Connection, pattern_id: str) -> sqlite3.Row | None:
    return connection.execute("SELECT * FROM patterns WHERE id = ?", (pattern_id,)).fetchone()


def count_pattern_transitions(connection: sqlite3.Connection, pattern_id: str) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM pattern_transitions WHERE pattern_id = ?",
        (pattern_id,),
    ).fetchone()
    return int(row["count"])
