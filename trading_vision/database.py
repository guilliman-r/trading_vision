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


def check_database_integrity(database_path: Path) -> None:
    """Raise sqlite3.DatabaseError if SQLite reports a corrupt database."""

    with connection_scope(database_path) as connection:
        result = database_integrity_result(connection)
    if result != "ok":
        raise sqlite3.DatabaseError(f"SQLite quick_check failed: {result}")


def database_integrity_result(connection: sqlite3.Connection) -> str:
    """Return SQLite PRAGMA quick_check output."""

    row = connection.execute("PRAGMA quick_check").fetchone()
    return str(row[0]) if row else "no quick_check result"


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


def backup_database(source_path: Path, destination_path: Path) -> Path:
    """Copy an existing SQLite database to a destination path."""

    if not source_path.exists():
        raise FileNotFoundError(f"Database does not exist: {source_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_path) as source, sqlite3.connect(destination_path) as destination:
        source.backup(destination)
    return destination_path


def table_counts(connection: sqlite3.Connection) -> list[tuple[str, int]]:
    """Return row counts for user-created tables in stable name order."""

    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    counts: list[tuple[str, int]] = []
    for row in rows:
        table_name = row["name"]
        count = connection.execute(
            f"SELECT COUNT(*) AS count FROM {_quote_identifier(table_name)}"
        ).fetchone()["count"]
        counts.append((table_name, int(count)))
    return counts


def database_file_size(database_path: Path) -> int:
    """Return the combined SQLite database, WAL, and shared-memory file size."""

    paths = (
        database_path,
        Path(f"{database_path}-wal"),
        Path(f"{database_path}-shm"),
    )
    return sum(path.stat().st_size for path in paths if path.exists())


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Manage the Trading Vision SQLite database")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("init", "backup", "stats"),
        default="init",
        help="Database command to run",
    )
    parser.add_argument("--path", type=Path, help="Optional database path")
    parser.add_argument("--output", type=Path, help="Backup destination path")
    arguments = parser.parse_args(argv)
    path = arguments.path or load_settings().database_path

    if arguments.command == "init":
        initialize_database(path)
        print(f"Database ready: {path}")
        return

    if not path.exists():
        raise FileNotFoundError(f"Database does not exist: {path}")

    if arguments.command == "backup":
        if arguments.output is None:
            parser.error("backup requires --output")
        backup_path = backup_database(path, arguments.output)
        print(f"Database backup written: {backup_path}")
        return

    with connect(path) as connection:
        print(f"Database: {path}")
        print(f"Size: {database_file_size(path)} bytes")
        print(f"Schema: {schema_version(connection)}")
        for table_name, count in table_counts(connection):
            print(f"{table_name}: {count}")


if __name__ == "__main__":
    main()
