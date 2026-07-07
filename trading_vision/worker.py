"""Command-line scanner loop for unattended or one-shot operation."""

from __future__ import annotations

import argparse
import logging
import signal
from datetime import UTC, datetime
from threading import Event

from trading_vision.config import SUPPORTED_INTERVALS, load_settings
from trading_vision.logging_setup import configure_logging
from trading_vision.market_calendar import BistSessionCalendar
from trading_vision.providers.yahoo import YahooFinanceProvider
from trading_vision.scanner_lock import ScannerAlreadyRunningError, ScannerLock
from trading_vision.scanner_schedule import next_poll_at
from trading_vision.services.scanner import ScannerService

LOGGER = logging.getLogger("trading_vision.worker")


def main(arguments: list[str] | None = None) -> int:
    parser = _argument_parser()
    options = parser.parse_args(arguments)
    settings = load_settings()
    configure_logging("scanner", settings.log_path, settings.log_level)
    intervals = tuple(options.intervals or settings.scan_intervals)
    symbols = tuple(options.symbols or ())
    stop = Event()
    _install_signal_handlers(stop)

    try:
        with ScannerLock(settings.scanner_lock_path):
            service = ScannerService(settings, YahooFinanceProvider())
            service.write_heartbeat("running", message="Scanner started")
            try:
                _run_loop(service, intervals, symbols, options, stop)
            finally:
                service.write_heartbeat("stopped", message="Scanner stopped")
    except ScannerAlreadyRunningError as error:
        LOGGER.error("scanner_lock_failed path=%s error=%s", settings.scanner_lock_path, error)
        return 2
    return 0


def _run_loop(service, intervals, symbols, options, stop: Event) -> None:
    calendar = BistSessionCalendar()
    while not stop.is_set():
        summary = service.run_once(
            symbol_queries=symbols,
            intervals=intervals,
            force=options.force,
            dry_run=options.dry_run,
            maximum_symbols=options.max_symbols,
        )
        for run in summary.runs:
            LOGGER.info(
                "scan_run run_id=%d interval=%s status=%s requested=%d succeeded=%d failed=%d "
                "candles_added=%d patterns_added=%d",
                run.run_id,
                run.interval,
                run.status,
                run.requested,
                run.succeeded,
                run.failed,
                run.candles_added,
                run.patterns_added,
            )
            for error in run.errors:
                LOGGER.warning("scan_error interval=%s error=%s", run.interval, error)
        if options.once:
            return
        now = datetime.now(UTC)
        next_wake = next_poll_at(
            now,
            intervals,
            service.settings.provider_delay_seconds,
            calendar,
        )
        service.write_heartbeat(
            "sleeping",
            next_wake_at=next_wake,
            message=f"Next boundary: {next_wake.isoformat()}",
        )
        wait_seconds = max(0.0, (next_wake - now).total_seconds())
        stop.wait(wait_seconds)


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan stored BIST symbols for chart patterns")
    parser.add_argument("--once", action="store_true", help="Run one due-job cycle and exit")
    parser.add_argument("--force", action="store_true", help="Scan selected jobs even when current")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Cache candles and run detectors without persisting pattern transitions",
    )
    parser.add_argument("--symbols", nargs="+", help="Stored display or provider symbols")
    parser.add_argument("--intervals", nargs="+", choices=SUPPORTED_INTERVALS)
    parser.add_argument(
        "--max-symbols",
        type=_positive_integer,
        help="Limit the selected universe for a smoke run",
    )
    return parser


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _install_signal_handlers(stop: Event) -> None:
    def request_stop(_signal_number, _frame) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)


if __name__ == "__main__":
    raise SystemExit(main())
