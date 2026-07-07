from __future__ import annotations

from dataclasses import replace

from trading_vision import worker
from trading_vision.database import connect
from trading_vision.models import Symbol
from trading_vision.repositories import seed_symbols
from trading_vision.scanner_repository import get_heartbeat, get_latest_scan_run

from .test_scanner_service import PartialProvider, scanner_settings


def test_one_shot_worker_runs_end_to_end_with_fake_provider(
    database_path, tmp_path, monkeypatch
) -> None:
    with connect(database_path) as connection:
        seed_symbols(connection, [Symbol("GOOD", "GOOD.IS", is_bist=True)])
        connection.commit()
    log_path = tmp_path / "worker.log"
    settings = replace(
        scanner_settings(database_path, tmp_path / "scanner.lock"),
        log_path=log_path,
    )
    monkeypatch.setattr(worker, "load_settings", lambda: settings)
    monkeypatch.setattr(worker, "YahooFinanceProvider", PartialProvider)
    monkeypatch.setattr(worker, "_install_signal_handlers", lambda _stop: None)

    exit_code = worker.main(["--once", "--force", "--symbols", "GOOD", "--intervals", "1d"])
    assert exit_code == 0
    with connect(database_path) as connection:
        run = get_latest_scan_run(connection)
        heartbeat = get_heartbeat(connection)
    assert run["status"] == "completed"
    assert run["symbols_succeeded"] == 1
    assert heartbeat["status"] == "stopped"
    assert f"scan_run run_id={run['id']}" in log_path.read_text(encoding="utf-8")


def test_worker_startup_initializes_database_and_imports_catalog(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "fresh" / "worker.sqlite3"
    log_path = tmp_path / "worker.log"
    settings = replace(
        scanner_settings(database_path, tmp_path / "scanner.lock"),
        log_path=log_path,
    )
    monkeypatch.setattr(worker, "load_settings", lambda: settings)
    monkeypatch.setattr(worker, "YahooFinanceProvider", PartialProvider)
    monkeypatch.setattr(worker, "_install_signal_handlers", lambda _stop: None)

    exit_code = worker.main(["--once", "--force", "--max-symbols", "1", "--intervals", "1d"])

    assert exit_code == 0
    with connect(database_path) as connection:
        migration_count = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        symbol_count = connection.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        run = get_latest_scan_run(connection)
    assert migration_count > 0
    assert symbol_count > 0
    assert run["symbols_requested"] == 1
