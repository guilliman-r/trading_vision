"""Short-lived, per-symbol chart result reuse for UI callbacks."""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock


class ChartLoadCooldown[Result]:
    """Serialize identical loads and reuse their result for a short interval."""

    def __init__(
        self,
        cooldown_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.clock = clock
        self._guard = Lock()
        self._key_locks: dict[tuple[str, str], Lock] = {}
        self._entries: dict[tuple[str, str], tuple[float, Result]] = {}

    def get_or_load(
        self,
        symbol: str,
        interval: str,
        loader: Callable[[], Result],
        force: bool = False,
    ) -> Result:
        key = (_canonical_symbol(symbol), interval)
        key_lock = self._lock_for(key)
        with key_lock:
            if not force:
                cached = self._fresh_result(key)
                if cached is not None:
                    return cached
            result = loader()
            with self._guard:
                self._entries[key] = (self.clock(), result)
            return result

    def _lock_for(self, key: tuple[str, str]) -> Lock:
        with self._guard:
            return self._key_locks.setdefault(key, Lock())

    def _fresh_result(self, key: tuple[str, str]) -> Result | None:
        with self._guard:
            entry = self._entries.get(key)
            if entry is None or self.cooldown_seconds <= 0:
                return None
            created_at, result = entry
            if self.clock() - created_at >= self.cooldown_seconds:
                self._entries.pop(key, None)
                return None
            return result


def _canonical_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    return normalized.removesuffix(".IS")
