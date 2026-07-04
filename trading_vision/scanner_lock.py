"""One-process file lock for the local scanner."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import TextIO


class ScannerAlreadyRunningError(RuntimeError):
    pass


class ScannerLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.file: TextIO | None = None

    def __enter__(self) -> ScannerLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            self.file.close()
            self.file = None
            raise ScannerAlreadyRunningError(f"Another scanner owns {self.path}") from error
        self.file.seek(0)
        self.file.truncate()
        self.file.write(str(os.getpid()))
        self.file.flush()
        return self

    def __exit__(self, _error_type, _error, _traceback) -> None:
        if self.file is None:
            return
        fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()
        self.file = None
