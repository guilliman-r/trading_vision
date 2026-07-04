from __future__ import annotations

import pytest

from trading_vision.scanner_lock import ScannerAlreadyRunningError, ScannerLock


def test_second_scanner_cannot_acquire_same_lock(tmp_path) -> None:
    path = tmp_path / "scanner.lock"
    with ScannerLock(path):
        contender = ScannerLock(path)
        with pytest.raises(ScannerAlreadyRunningError):
            contender.__enter__()

    with ScannerLock(path):
        assert path.read_text() != ""
