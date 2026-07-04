"""Alert rule, event, acknowledgement, and mute persistence."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from trading_vision.models import AlertEvent, AlertRule, PatternMatch, PatternTransition, Symbol

DEFAULT_RULE_NAME = "Confirmed enabled patterns"


def ensure_default_rule(
    connection: sqlite3.Connection,
    minimum_score: float,
    pattern_types: tuple[str, ...],
) -> AlertRule:
    now = datetime.now(UTC).isoformat()
    connection.execute(
        """
        INSERT INTO alert_rules (
            name, minimum_score, required_state, pattern_types_json,
            is_active, created_at_utc, updated_at_utc
        ) VALUES (?, ?, 'confirmed', ?, 1, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            minimum_score = excluded.minimum_score,
            pattern_types_json = excluded.pattern_types_json,
            updated_at_utc = excluded.updated_at_utc
        """,
        (
            DEFAULT_RULE_NAME,
            minimum_score,
            json.dumps(pattern_types),
            now,
            now,
        ),
    )
    row = connection.execute(
        "SELECT * FROM alert_rules WHERE name = ?", (DEFAULT_RULE_NAME,)
    ).fetchone()
    return _rule_from_row(row)


def list_active_rules(connection: sqlite3.Connection) -> list[AlertRule]:
    rows = connection.execute(
        "SELECT * FROM alert_rules WHERE is_active = 1 ORDER BY id"
    ).fetchall()
    return [_rule_from_row(row) for row in rows]


def is_pattern_muted(connection: sqlite3.Connection, pattern_id: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM pattern_mutes WHERE pattern_id = ?", (pattern_id,)
    ).fetchone()
    return row is not None


def insert_alert_event(
    connection: sqlite3.Connection,
    fingerprint: str,
    rule: AlertRule,
    transition: PatternTransition,
    symbol: Symbol,
    interval: str,
    match: PatternMatch,
) -> bool:
    event_at = match.confirmed_at or transition.changed_at
    app_link = (
        f"/?symbol={symbol.provider_symbol}&interval={interval}&pattern={transition.pattern_id}"
    )
    cursor = connection.execute(
        """
        INSERT INTO alert_events (
            fingerprint, rule_id, transition_id, pattern_id, symbol_id,
            provider_symbol, interval, pattern_type, direction, state, score,
            event_at_utc, boundary_price, target_price, app_link, created_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(fingerprint) DO NOTHING
        """,
        (
            fingerprint,
            rule.id,
            transition.id,
            transition.pattern_id,
            symbol.id,
            symbol.provider_symbol,
            interval,
            match.pattern_type,
            match.direction,
            match.state,
            match.score,
            event_at.isoformat(),
            match.boundary_price,
            match.target_price,
            app_link,
            transition.changed_at.isoformat(),
        ),
    )
    return cursor.rowcount == 1


def list_recent_alerts(connection: sqlite3.Connection, limit: int = 20) -> list[AlertEvent]:
    rows = connection.execute(
        "SELECT * FROM alert_events ORDER BY created_at_utc DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_event_from_row(row) for row in rows]


def unread_alert_count(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM alert_events WHERE acknowledged_at_utc IS NULL"
    ).fetchone()
    return int(row["count"])


def acknowledge_alert(connection: sqlite3.Connection, alert_id: int) -> None:
    connection.execute(
        """
        UPDATE alert_events SET acknowledged_at_utc = COALESCE(acknowledged_at_utc, ?)
        WHERE id = ?
        """,
        (datetime.now(UTC).isoformat(), alert_id),
    )


def acknowledge_all_alerts(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        UPDATE alert_events SET acknowledged_at_utc = ?
        WHERE acknowledged_at_utc IS NULL
        """,
        (datetime.now(UTC).isoformat(),),
    )


def mute_alert_pattern(connection: sqlite3.Connection, alert_id: int) -> None:
    row = connection.execute(
        "SELECT pattern_id FROM alert_events WHERE id = ?", (alert_id,)
    ).fetchone()
    if row is None:
        return
    now = datetime.now(UTC).isoformat()
    connection.execute(
        """
        INSERT INTO pattern_mutes(pattern_id, muted_at_utc, reason)
        VALUES (?, ?, 'Muted from alert center')
        ON CONFLICT(pattern_id) DO NOTHING
        """,
        (row["pattern_id"], now),
    )
    connection.execute(
        """
        UPDATE alert_events SET acknowledged_at_utc = COALESCE(acknowledged_at_utc, ?)
        WHERE pattern_id = ?
        """,
        (now, row["pattern_id"]),
    )


def mute_pattern(connection: sqlite3.Connection, pattern_id: str, reason: str) -> None:
    connection.execute(
        """
        INSERT INTO pattern_mutes(pattern_id, muted_at_utc, reason)
        VALUES (?, ?, ?)
        ON CONFLICT(pattern_id) DO UPDATE SET
            muted_at_utc = excluded.muted_at_utc,
            reason = excluded.reason
        """,
        (pattern_id, datetime.now(UTC).isoformat(), reason),
    )


def _rule_from_row(row: sqlite3.Row) -> AlertRule:
    return AlertRule(
        id=int(row["id"]),
        name=row["name"],
        minimum_score=float(row["minimum_score"]),
        required_state=row["required_state"],
        pattern_types=tuple(json.loads(row["pattern_types_json"])),
        is_active=bool(row["is_active"]),
    )


def _event_from_row(row: sqlite3.Row) -> AlertEvent:
    return AlertEvent(
        id=int(row["id"]),
        fingerprint=row["fingerprint"],
        pattern_id=row["pattern_id"],
        provider_symbol=row["provider_symbol"],
        interval=row["interval"],
        pattern_type=row["pattern_type"],
        direction=row["direction"],
        state=row["state"],
        score=float(row["score"]),
        event_at=datetime.fromisoformat(row["event_at_utc"]),
        boundary_price=float(row["boundary_price"]),
        target_price=float(row["target_price"]) if row["target_price"] is not None else None,
        app_link=row["app_link"],
        created_at=datetime.fromisoformat(row["created_at_utc"]),
        acknowledged_at=(
            datetime.fromisoformat(row["acknowledged_at_utc"])
            if row["acknowledged_at_utc"]
            else None
        ),
    )
