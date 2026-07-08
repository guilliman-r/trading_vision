"""Sequential background scan pipeline with per-symbol failure isolation."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime

from trading_vision.candle_completion import mark_bist_candle_completion
from trading_vision.config import PROJECT_ROOT, Settings
from trading_vision.database import check_database_integrity, connection_scope, initialize_database
from trading_vision.market_calendar import BistSessionCalendar
from trading_vision.providers.base import FetchResult, MarketDataProvider
from trading_vision.repositories import (
    find_symbol,
    get_candles,
    import_symbol_catalog,
    upsert_candles,
)
from trading_vision.scanner_models import JobResult, ScanCycleSummary, ScanJob, ScanRunSummary
from trading_vision.scanner_repository import (
    count_candles,
    finish_scan_run,
    latest_completed_candle_at,
    list_active_bist_symbols,
    start_scan_run,
    update_heartbeat,
)
from trading_vision.scanner_schedule import is_job_due
from trading_vision.services.pattern_scan import PatternScanService


class ScannerService:
    def __init__(
        self,
        settings: Settings,
        provider: MarketDataProvider,
        calendar: BistSessionCalendar | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings.validate()
        self.provider = provider
        self.calendar = calendar or BistSessionCalendar()
        self.now = now or (lambda: datetime.now(UTC))
        self.process_started_at = self.now()
        initialize_database(settings.database_path)
        with connection_scope(settings.database_path) as connection:
            import_symbol_catalog(
                connection,
                PROJECT_ROOT / "data" / "catalogs" / "bist_symbols.csv",
            )
        check_database_integrity(settings.database_path)

    def run_once(
        self,
        symbol_queries: tuple[str, ...] = (),
        intervals: tuple[str, ...] | None = None,
        force: bool = False,
        dry_run: bool = False,
        maximum_symbols: int | None = None,
    ) -> ScanCycleSummary:
        selected_intervals = intervals or self.settings.scan_intervals
        symbols = self._load_symbols(symbol_queries)
        if maximum_symbols is not None:
            symbols = symbols[:maximum_symbols]
        jobs = self._due_jobs(symbols, selected_intervals, force)
        runs = [
            self._run_interval(interval, jobs.get(interval, []), dry_run)
            for interval in selected_intervals
        ]
        last_run_id = runs[-1].run_id if runs else None
        self.write_heartbeat(
            "idle",
            last_run_id=last_run_id,
            message=(
                f"Cycle complete: {sum(run.succeeded for run in runs)} succeeded, "
                f"{sum(run.failed for run in runs)} failed"
            ),
        )
        return ScanCycleSummary(tuple(runs))

    def write_heartbeat(
        self,
        status: str,
        next_wake_at: datetime | None = None,
        last_run_id: int | None = None,
        message: str | None = None,
    ) -> None:
        with connection_scope(self.settings.database_path) as connection:
            update_heartbeat(
                connection,
                status=status,
                process_id=os.getpid(),
                started_at=self.process_started_at,
                updated_at=self.now(),
                next_wake_at=next_wake_at,
                last_run_id=last_run_id,
                message=message,
            )

    def _load_symbols(self, queries: tuple[str, ...]):
        with connection_scope(self.settings.database_path) as connection:
            if not queries:
                return list_active_bist_symbols(connection)
            symbols = []
            for query in queries:
                symbol = find_symbol(connection, query)
                if symbol is None:
                    raise ValueError(f"Unknown stored symbol: {query}")
                symbols.append(symbol)
            return symbols

    def _due_jobs(self, symbols, intervals: tuple[str, ...], force: bool):
        jobs = {interval: [] for interval in intervals}
        cycle_time = self.now()
        with connection_scope(self.settings.database_path) as connection:
            for interval in intervals:
                for symbol in symbols:
                    latest = latest_completed_candle_at(connection, symbol.id, interval)
                    if force or is_job_due(
                        latest,
                        interval,
                        cycle_time,
                        self.settings.provider_delay_seconds,
                        self.calendar,
                    ):
                        jobs[interval].append(ScanJob(symbol, interval))
        return jobs

    def _run_interval(
        self,
        interval: str,
        jobs: list[ScanJob],
        dry_run: bool,
    ) -> ScanRunSummary:
        started_at = self.now()
        with connection_scope(self.settings.database_path) as connection:
            run_id = start_scan_run(
                connection,
                started_at,
                interval,
                self.provider.name,
                len(jobs),
                dry_run,
            )

        succeeded = 0
        failures: list[str] = []
        warnings: list[str] = []
        candles_added = 0
        patterns_added = 0
        for batch in _batches(jobs, self.settings.scanner_batch_size):
            fetched_by_symbol = self._fetch_batch(batch, interval)
            for job in batch:
                try:
                    fetched = fetched_by_symbol.get(job.symbol.provider_symbol)
                    if fetched is None:
                        fetched = FetchResult(
                            symbol=job.symbol.provider_symbol,
                            error="Provider batch result was missing this symbol",
                            failure_kind="partial_batch_failure",
                        )
                    result = self._run_job(job, dry_run, fetched)
                    succeeded += 1
                    candles_added += result.candles_added
                    patterns_added += result.patterns_added
                    warnings.extend(result.warnings)
                except Exception as error:  # one provider/symbol must not abort the universe
                    failures.append(f"{job.symbol.provider_symbol}: {error}")

        status = _run_status(succeeded, len(failures))
        with connection_scope(self.settings.database_path) as connection:
            finish_scan_run(
                connection,
                run_id,
                self.now(),
                succeeded,
                len(failures),
                candles_added,
                patterns_added,
                status,
                failures,
                warnings,
            )
        return ScanRunSummary(
            run_id=run_id,
            interval=interval,
            requested=len(jobs),
            succeeded=succeeded,
            failed=len(failures),
            candles_added=candles_added,
            patterns_added=patterns_added,
            status=status,
            errors=tuple(failures),
            warnings=tuple(warnings),
        )

    def _fetch_batch(self, batch: list[ScanJob], interval: str) -> dict[str, FetchResult]:
        symbols = tuple(job.symbol.provider_symbol for job in batch)
        try:
            return self.provider.fetch_history_batch(
                symbols,
                interval,
                batch_size=self.settings.scanner_batch_size,
            )
        except Exception as error:  # one batch must not abort the scanner cycle
            return {
                symbol: FetchResult(
                    symbol=symbol,
                    error=f"Provider batch failure: {error}",
                    failure_kind="partial_batch_failure",
                )
                for symbol in symbols
            }

    def _run_job(self, job: ScanJob, dry_run: bool, fetched: FetchResult) -> JobResult:
        if not fetched.succeeded:
            raise RuntimeError(fetched.error or "Provider returned no candles")
        _require_storage_columns(fetched.candles)
        prepared = self._apply_bist_completion(fetched.candles, job.interval)

        with connection_scope(self.settings.database_path) as connection:
            before = count_candles(connection, job.symbol.id, job.interval)
            upsert_candles(connection, job.symbol.id, job.interval, prepared)
            after = count_candles(connection, job.symbol.id, job.interval)
            candles = get_candles(
                connection,
                job.symbol.id,
                job.interval,
                self.settings.scanner_lookback_bars,
            )
            pattern_scan = PatternScanService(
                connection,
                minimum_alert_score=self.settings.minimum_alert_score,
                alert_pattern_types=self.settings.alert_pattern_types,
            )
            if dry_run:
                pattern_scan.detect(candles)
                transitions = 0
            else:
                transitions = pattern_scan.scan(job.symbol, job.interval, candles).state_transitions
        warnings = ()
        if fetched.quality_report is not None and fetched.quality_report.has_warnings:
            warnings = (f"{job.symbol.provider_symbol}: {fetched.quality_report.summary()}",)
        return JobResult(max(0, after - before), transitions, warnings)

    def _apply_bist_completion(self, candles, interval: str):
        return mark_bist_candle_completion(
            candles,
            interval,
            self.now(),
            self.settings.provider_delay_seconds,
            self.calendar,
        )


def _batches(jobs: list[ScanJob], size: int):
    for start in range(0, len(jobs), size):
        yield jobs[start : start + size]


def _require_storage_columns(candles) -> None:
    required = {
        "opened_at_utc",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "is_complete",
        "is_adjusted",
        "source",
        "fetched_at_utc",
    }
    missing = required.difference(candles.columns)
    if missing:
        raise ValueError(f"Prepared candles are missing: {', '.join(sorted(missing))}")


def _run_status(succeeded: int, failed: int) -> str:
    if failed == 0:
        return "completed"
    if succeeded == 0:
        return "failed"
    return "partial"
