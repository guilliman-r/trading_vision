from __future__ import annotations

import csv
from pathlib import Path
from runpy import run_path

import pandas as pd

from trading_vision.providers.base import FetchResult, MarketDataProvider

SCRIPT = Path("scripts/validate_catalog_provider_symbols.py")


class FakeProvider(MarketDataProvider):
    name = "fake"

    def __init__(self) -> None:
        self.batches: list[tuple[tuple[str, ...], str, int]] = []

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        raise NotImplementedError

    def fetch_history_batch(
        self,
        symbols: tuple[str, ...],
        interval: str,
        batch_size: int,
    ) -> dict[str, FetchResult]:
        self.batches.append((symbols, interval, batch_size))
        results = {}
        for symbol in symbols:
            if symbol == "BAD.IS":
                results[symbol] = FetchResult(
                    symbol=symbol,
                    error="invalid ticker",
                    failure_kind="invalid_ticker",
                )
            else:
                results[symbol] = FetchResult(
                    symbol=symbol,
                    candles=pd.DataFrame({"close": [10.0, 11.0]}),
                )
        return results


def test_provider_validation_batches_symbols_and_records_failures() -> None:
    module = run_path(str(SCRIPT))
    provider = FakeProvider()

    rows = module["validate_symbols"](
        provider,
        ["GOOD.IS", "BAD.IS", "NEXT.IS"],
        "1d",
        batch_size=2,
    )

    assert provider.batches == [
        (("GOOD.IS", "BAD.IS"), "1d", 2),
        (("NEXT.IS",), "1d", 2),
    ]
    assert [row.status for row in rows] == ["ok", "failed", "ok"]
    assert rows[1].failure_kind == "invalid_ticker"
    assert rows[1].error == "invalid ticker"
    assert rows[0].candles == 2


def test_provider_validation_writes_csv(tmp_path) -> None:
    module = run_path(str(SCRIPT))
    output = tmp_path / "validation.csv"
    rows = [
        module["ValidationRow"]("GOOD.IS", "ok", "", "", 2),
        module["ValidationRow"]("BAD.IS", "failed", "invalid_ticker", "invalid ticker", 0),
    ]

    module["write_validation_rows"](rows, output)

    with output.open(encoding="utf-8", newline="") as file:
        written = list(csv.DictReader(file))
    assert written[0]["provider_symbol"] == "GOOD.IS"
    assert written[1]["failure_kind"] == "invalid_ticker"
