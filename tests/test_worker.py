from __future__ import annotations

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
    settings = scanner_settings(database_path, tmp_path / "scanner.lock")
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
