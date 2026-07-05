from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event

from trading_vision.services.chart_load_cache import ChartLoadCooldown


def test_reuses_result_until_cooldown_expires_and_force_bypasses() -> None:
    now = [100.0]
    calls: list[int] = []
    cache = ChartLoadCooldown[int](30, clock=lambda: now[0])

    def load() -> int:
        calls.append(len(calls) + 1)
        return calls[-1]

    assert cache.get_or_load("thyao", "1d", load) == 1
    assert cache.get_or_load("THYAO.IS", "1d", load) == 1
    assert cache.get_or_load("THYAO", "1d", load, force=True) == 2
    now[0] += 31
    assert cache.get_or_load("THYAO", "1d", load) == 3
    assert calls == [1, 2, 3]


def test_different_intervals_use_independent_entries() -> None:
    calls: list[str] = []
    cache = ChartLoadCooldown[str](30)

    daily = cache.get_or_load("THYAO", "1d", lambda: calls.append("1d") or "daily")
    hourly = cache.get_or_load("THYAO", "1h", lambda: calls.append("1h") or "hourly")

    assert (daily, hourly) == ("daily", "hourly")
    assert calls == ["1d", "1h"]


def test_concurrent_identical_loads_share_one_result() -> None:
    started = Event()
    release = Event()
    calls = [0]
    cache = ChartLoadCooldown[str](30)

    def load() -> str:
        calls[0] += 1
        started.set()
        release.wait(timeout=2)
        return "loaded"

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(cache.get_or_load, "THYAO", "1d", load)
        assert started.wait(timeout=2)
        second = executor.submit(cache.get_or_load, "THYAO", "1d", load)
        release.set()

    assert first.result() == second.result() == "loaded"
    assert calls[0] == 1
