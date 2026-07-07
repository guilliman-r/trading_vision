"""SQLite connection and deliberately small migration runner."""

from __future__ import annotations

import argparse
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from trading_vision.config import PROJECT_ROOT, load_settings

MIGRATIONS_DIRECTORY = PROJECT_ROOT / "migrations"


def connect(database_path: Path) -> sqlite3.Connection:
    """Open a configured SQLite connection."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


@contextmanager
def connection_scope(database_path: Path) -> Iterator[sqlite3.Connection]:
    """Open, commit or roll back, and always close one SQLite connection."""

    connection = connect(database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(database_path: Path) -> None:
    """Apply every not-yet-recorded SQL migration in filename order."""

    with connection_scope(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        applied = {
            row["filename"] for row in connection.execute("SELECT filename FROM schema_migrations")
        }
        for migration_path in sorted(MIGRATIONS_DIRECTORY.glob("*.sql")):
            if migration_path.name in applied:
                continue
            connection.executescript(migration_path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations(filename) VALUES (?)",
                (migration_path.name,),
            )


def schema_version(connection: sqlite3.Connection) -> str:
    """Return a concise human-readable migration state."""

    row = connection.execute(
        """
        SELECT filename
        FROM schema_migrations
        ORDER BY filename DESC
        LIMIT 1
        """
    ).fetchone()
    count = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    if row is None:
        return "No migrations applied"
    migration_word = "migration" if count == 1 else "migrations"
    return f"{row['filename']} · {count} {migration_word}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the Trading Vision database")
    parser.add_argument("--path", type=Path, help="Optional database path")
    arguments = parser.parse_args()
    path = arguments.path or load_settings().database_path
    initialize_database(path)
    print(f"Database ready: {path}")


if __name__ == "__main__":
    main()
