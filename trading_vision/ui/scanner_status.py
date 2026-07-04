"""Turn the persisted worker heartbeat into a short UI label."""

from __future__ import annotations

import sqlite3

import pandas as pd


def scanner_status_text(heartbeat: sqlite3.Row | None) -> str:
    if heartbeat is None:
        return "Scanner not started"
    updated = pd.Timestamp(heartbeat["updated_at_utc"])
    if updated.tzinfo is None:
        updated = updated.tz_localize("UTC")
    local_time = updated.tz_convert("Europe/Istanbul").strftime("%d %b · %H:%M")
    status = str(heartbeat["status"]).replace("_", " ").title()
    return f"Scanner {status} · {local_time}"
