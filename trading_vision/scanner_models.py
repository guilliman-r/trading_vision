"""Small value objects shared by scanner scheduling, persistence, and the CLI."""

from __future__ import annotations

from dataclasses import dataclass

from trading_vision.models import Symbol


@dataclass(frozen=True, slots=True)
class ScanJob:
    symbol: Symbol
    interval: str


@dataclass(frozen=True, slots=True)
class ScanRunSummary:
    run_id: int
    interval: str
    requested: int
    succeeded: int
    failed: int
    candles_added: int
    patterns_added: int
    status: str
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScanCycleSummary:
    runs: tuple[ScanRunSummary, ...]

    @property
    def requested(self) -> int:
        return sum(run.requested for run in self.runs)

    @property
    def succeeded(self) -> int:
        return sum(run.succeeded for run in self.runs)


@dataclass(frozen=True, slots=True)
class JobResult:
    candles_added: int
    patterns_added: int
    warnings: tuple[str, ...] = ()
