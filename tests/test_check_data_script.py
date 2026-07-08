from __future__ import annotations

from pathlib import Path
from runpy import run_path

from trading_vision.database import connect
from trading_vision.models import Symbol
from trading_vision.repositories import upsert_symbol

SCRIPT = Path("scripts/check_data.py")


def test_check_data_reports_coverage_and_quality_counts(database_path) -> None:
    module = run_path(str(SCRIPT))
    with connect(database_path) as connection:
        symbol = upsert_symbol(connection, Symbol("TEST", "TEST.IS", is_bist=True))
        connection.executemany(
            """
            INSERT INTO candles (
                symbol_id, interval, opened_at_utc, open, high, low, close, volume,
                is_complete, is_adjusted, source, fetched_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    symbol.id,
                    "1d",
                    "2026-07-07T00:00:00+00:00",
                    10.0,
                    12.0,
                    9.0,
                    11.0,
                    100.0,
                    1,
                    1,
                    "fixture",
                    "2026-07-07T16:00:00+00:00",
                ),
                (
                    symbol.id,
                    "1d",
                    "2026-07-08T00:00:00+00:00",
                    -1.0,
                    8.0,
                    9.0,
                    7.0,
                    None,
                    0,
                    1,
                    "fixture",
                    "2026-07-08T16:00:00+00:00",
                ),
            ],
        )

        rows = module["build_rows"](connection)

    assert len(rows) == 1
    row = rows[0]
    assert row.symbol == "TEST.IS"
    assert row.rows == 2
    assert row.complete == 1
    assert row.forming == 1
    assert row.missing_volume == 1
    assert row.bad_ohlc == 1
    assert row.nonpositive_price == 1
    assert row.quality_status == "check"

    output = module["format_rows"](rows)
    assert "TEST.IS" in output
    assert "bad_ohlc" in output
    assert "check" in output


def test_check_data_filters_by_symbol_and_interval(database_path) -> None:
    module = run_path(str(SCRIPT))
    with connect(database_path) as connection:
        first = upsert_symbol(connection, Symbol("ONE", "ONE.IS", is_bist=True))
        second = upsert_symbol(connection, Symbol("TWO", "TWO.IS", is_bist=True))
        for symbol_id, interval in ((first.id, "1d"), (second.id, "1h")):
            connection.execute(
                """
                INSERT INTO candles (
                    symbol_id, interval, opened_at_utc, open, high, low, close, volume,
                    is_complete, is_adjusted, source, fetched_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol_id,
                    interval,
                    "2026-07-08T00:00:00+00:00",
                    10.0,
                    12.0,
                    9.0,
                    11.0,
                    100.0,
                    1,
                    1,
                    "fixture",
                    "2026-07-08T16:00:00+00:00",
                ),
            )

        rows = module["build_rows"](connection, symbols=("TWO.IS",), intervals=("1h",))

    assert [row.symbol for row in rows] == ["TWO.IS"]
    assert [row.interval for row in rows] == ["1h"]


def test_check_data_prints_clear_empty_message() -> None:
    module = run_path(str(SCRIPT))

    assert module["format_rows"]([]) == "No candles found."
