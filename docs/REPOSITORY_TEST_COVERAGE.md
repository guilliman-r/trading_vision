# Repository test coverage

Every repository module has focused tests and at least one fresh temporary SQLite database path
through the shared `database_path` fixture.

The direct smoke guard lives in `tests/test_repository_smoke.py` and touches:

- `trading_vision.repositories`
- `trading_vision.pattern_repository`
- `trading_vision.alert_repository`
- `trading_vision.scanner_repository`
- `trading_vision.scanner_results_repository`
- `trading_vision.watchlist_repository`
- `trading_vision.drawing_repository`

Focused repository behavior is also covered in:

- `tests/test_database.py`
- `tests/test_pattern_persistence.py`
- `tests/test_alerts.py`
- `tests/test_scanner_results.py`
- `tests/test_watchlist_repository.py`
- `tests/test_drawing_repository.py`
