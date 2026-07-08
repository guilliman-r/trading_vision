"""Print stored candle coverage and simple quality counts."""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from trading_vision.config import load_settings
from trading_vision.database import connect


@dataclass(frozen=True, slots=True)
class DataCoverageRow:
    symbol: str
    interval: str
    rows: int
    complete: int
    forming: int
    first_opened_at: str
    latest_opened_at: str
    latest_fetched_at: str
    missing_volume: int
    bad_ohlc: int
    nonpositive_price: int

    @property
    def quality_status(self) -> str:
        if self.bad_ohlc or self.nonpositive_price:
            return "check"
        if self.missing_volume:
            return "volume-missing"
        return "ok"


def build_rows(
    connection: sqlite3.Connection,
    symbols: tuple[str, ...] = (),
    intervals: tuple[str, ...] = (),
) -> list[DataCoverageRow]:
    clauses: list[str] = []
    parameters: list[str] = []
    if symbols:
        clauses.append(f"s.provider_symbol IN ({_placeholders(symbols)})")
        parameters.extend(symbols)
    if intervals:
        clauses.append(f"c.interval IN ({_placeholders(intervals)})")
        parameters.extend(intervals)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = connection.execute(
        f"""
        SELECT
            s.provider_symbol,
            c.interval,
            COUNT(*) AS rows,
            SUM(CASE WHEN c.is_complete = 1 THEN 1 ELSE 0 END) AS complete,
            SUM(CASE WHEN c.is_complete = 0 THEN 1 ELSE 0 END) AS forming,
            MIN(c.opened_at_utc) AS first_opened_at,
            MAX(c.opened_at_utc) AS latest_opened_at,
            MAX(c.fetched_at_utc) AS latest_fetched_at,
            SUM(CASE WHEN c.volume IS NULL THEN 1 ELSE 0 END) AS missing_volume,
            SUM(
                CASE
                    WHEN c.high < c.low
                      OR c.high < c.open
                      OR c.high < c.close
                      OR c.low > c.open
                      OR c.low > c.close
                    THEN 1 ELSE 0
                END
            ) AS bad_ohlc,
            SUM(
                CASE
                    WHEN c.open <= 0 OR c.high <= 0 OR c.low <= 0 OR c.close <= 0
                    THEN 1 ELSE 0
                END
            ) AS nonpositive_price
        FROM candles c
        JOIN symbols s ON s.id = c.symbol_id
        {where}
        GROUP BY s.provider_symbol, c.interval
        ORDER BY s.provider_symbol, c.interval
        """,
        parameters,
    ).fetchall()
    return [
        DataCoverageRow(
            symbol=row["provider_symbol"],
            interval=row["interval"],
            rows=int(row["rows"]),
            complete=int(row["complete"]),
            forming=int(row["forming"]),
            first_opened_at=str(row["first_opened_at"]),
            latest_opened_at=str(row["latest_opened_at"]),
            latest_fetched_at=str(row["latest_fetched_at"]),
            missing_volume=int(row["missing_volume"]),
            bad_ohlc=int(row["bad_ohlc"]),
            nonpositive_price=int(row["nonpositive_price"]),
        )
        for row in rows
    ]


def format_rows(rows: list[DataCoverageRow]) -> str:
    if not rows:
        return "No candles found."
    headers = (
        "symbol",
        "interval",
        "rows",
        "complete",
        "forming",
        "first",
        "latest",
        "fetched",
        "missing_volume",
        "bad_ohlc",
        "nonpositive_price",
        "quality",
    )
    values = [
        (
            row.symbol,
            row.interval,
            str(row.rows),
            str(row.complete),
            str(row.forming),
            row.first_opened_at,
            row.latest_opened_at,
            row.latest_fetched_at,
            str(row.missing_volume),
            str(row.bad_ohlc),
            str(row.nonpositive_price),
            row.quality_status,
        )
        for row in rows
    ]
    widths = [
        max(len(headers[index]), *(len(value[index]) for value in values))
        for index in range(len(headers))
    ]
    separator = tuple("-" * width for width in widths)
    lines = [_format_line(headers, widths), _format_line(separator, widths)]
    lines.extend(_format_line(value, widths) for value in values)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print stored candle coverage and quality counts")
    parser.add_argument("--config", type=Path, help="Optional config.toml path")
    parser.add_argument(
        "--symbol",
        action="append",
        default=[],
        help="Provider symbol to include, e.g. THYAO.IS. Can be passed more than once.",
    )
    parser.add_argument(
        "--interval",
        action="append",
        default=[],
        help="Interval to include, e.g. 1d or 1h. Can be passed more than once.",
    )
    arguments = parser.parse_args(argv)

    settings = load_settings(arguments.config)
    with connect(settings.database_path) as connection:
        rows = build_rows(
            connection,
            tuple(symbol.upper() for symbol in arguments.symbol),
            tuple(arguments.interval),
        )
    print(format_rows(rows))
    return 0


def _format_line(values: tuple[str, ...], widths: list[int]) -> str:
    return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values))


def _placeholders(values: tuple[str, ...]) -> str:
    return ", ".join("?" for _value in values)


if __name__ == "__main__":
    raise SystemExit(main())
