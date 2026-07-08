"""Validate catalog provider symbols in bounded Yahoo batches."""

from __future__ import annotations

import argparse
import csv
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from time import sleep

from trading_vision.providers.base import FetchResult, MarketDataProvider
from trading_vision.providers.yahoo import YahooFinanceProvider

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PROJECT_ROOT / "data" / "catalogs" / "bist_symbols.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "var" / "bist_provider_validation.csv"


@dataclass(frozen=True, slots=True)
class ValidationRow:
    provider_symbol: str
    status: str
    failure_kind: str
    error: str
    candles: int


def read_provider_symbols(catalog_path: Path, max_symbols: int | None = None) -> list[str]:
    with catalog_path.open(encoding="utf-8", newline="") as file:
        symbols = [row["provider_symbol"] for row in csv.DictReader(file) if row["provider_symbol"]]
    return symbols[:max_symbols] if max_symbols is not None else symbols


def validate_symbols(
    provider: MarketDataProvider,
    symbols: Sequence[str],
    interval: str,
    batch_size: int,
    sleep_seconds: float = 0.0,
) -> list[ValidationRow]:
    rows: list[ValidationRow] = []
    for batch in _batches(symbols, batch_size):
        results = provider.fetch_history_batch(batch, interval, batch_size)
        rows.extend(_validation_row(symbol, results.get(symbol)) for symbol in batch)
        if sleep_seconds > 0:
            sleep(sleep_seconds)
    return rows


def write_validation_rows(rows: list[ValidationRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=("provider_symbol", "status", "failure_kind", "error", "candles"),
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "provider_symbol": row.provider_symbol,
                    "status": row.status,
                    "failure_kind": row.failure_kind,
                    "error": row.error,
                    "candles": row.candles,
                }
            )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--max-symbols", type=int, help="Limit validation for a smoke run")
    arguments = parser.parse_args(argv)

    symbols = read_provider_symbols(arguments.catalog, arguments.max_symbols)
    rows = validate_symbols(
        YahooFinanceProvider(max_attempts=1),
        symbols,
        arguments.interval,
        max(1, min(arguments.batch_size, 100)),
        max(0.0, arguments.sleep_seconds),
    )
    write_validation_rows(rows, arguments.output)
    failures = sum(1 for row in rows if row.status == "failed")
    print(f"Validated {len(rows)} symbols; failures={failures}; output={arguments.output}")


def _validation_row(symbol: str, result: FetchResult | None) -> ValidationRow:
    if result is None:
        return ValidationRow(symbol, "failed", "missing_result", "Provider returned no result", 0)
    if result.succeeded:
        return ValidationRow(symbol, "ok", "", "", len(result.candles))
    return ValidationRow(
        symbol,
        "failed",
        result.failure_kind or "provider_error",
        result.error or "Provider returned no candles",
        0,
    )


def _batches(symbols: Sequence[str], batch_size: int):
    size = max(1, batch_size)
    for start in range(0, len(symbols), size):
        yield tuple(symbols[start : start + size])


if __name__ == "__main__":
    main()
