import csv
from pathlib import Path
from runpy import run_path

import pytest

from trading_vision.database import connect
from trading_vision.repositories import (
    find_symbol,
    import_symbol_catalog,
    list_active_symbols,
)

PROJECT_ROOT = Path(__file__).parents[1]
CATALOG_PATH = PROJECT_ROOT / "data" / "catalogs" / "bist_symbols.csv"


def test_kap_catalog_parser_extracts_multiple_stock_codes() -> None:
    module = run_path(str(PROJECT_ROOT / "scripts" / "refresh_bist_symbols.py"))
    page = (
        r"\"kapMemberTitle\":\"Example Company\","
        r"\"relatedMemberTitle\":\"Auditor\","
        r"\"stockCode\":\"AAAAB BBBBC BAD\""
    )
    rows = module["parse_companies"](page)
    assert [row["display_symbol"] for row in rows] == ["AAAAB", "BBBBC"]
    assert [row["provider_symbol"] for row in rows] == ["AAAAB.IS", "BBBBC.IS"]
    assert {row["asset_type"] for row in rows} == {"equity"}
    assert {row["exchange"] for row in rows} == {"XIST"}
    assert {row["currency"] for row in rows} == {"TRY"}


def test_kap_catalog_parser_skips_invalid_codes_and_deduplicates() -> None:
    module = run_path(str(PROJECT_ROOT / "scripts" / "refresh_bist_symbols.py"))
    page = (
        r"\"kapMemberTitle\":\"First Company\","
        r"\"stockCode\":\"AAAAB BAD TOO-LONG lower\""
        r"\"kapMemberTitle\":\"Second Company\","
        r"\"stockCode\":\"AAAAB CCCCD\""
    )

    rows = module["parse_companies"](page)

    assert [row["provider_symbol"] for row in rows] == ["AAAAB.IS", "CCCCD.IS"]
    assert rows[0]["name"] == "Second Company"


def test_catalog_import_preserves_inactive_symbols_without_scanning_them(
    database_path,
    tmp_path,
) -> None:
    catalog = tmp_path / "catalog.csv"
    catalog.write_text(
        "\n".join(
            (
                "display_symbol,provider_symbol,name,exchange,currency,asset_type,is_bist,"
                "is_active,source,source_date",
                "OLD,OLD.IS,Old Company,XIST,TRY,equity,true,false,fixture,2026-07-07",
            )
        ),
        encoding="utf-8",
    )

    with connect(database_path) as connection:
        imported = import_symbol_catalog(connection, catalog)
        stored = find_symbol(connection, "OLD")
        active_symbols = list_active_symbols(connection)

    assert imported == 1
    assert stored is not None
    assert not stored.is_active
    assert active_symbols == []


def test_catalog_refresh_report_records_additions_removals_and_changes(tmp_path) -> None:
    module = run_path(str(PROJECT_ROOT / "scripts" / "refresh_bist_symbols.py"))
    before = [
        {
            "display_symbol": "OLD",
            "provider_symbol": "OLD.IS",
            "name": "Old Company",
            "exchange": "XIST",
            "currency": "TRY",
            "asset_type": "equity",
            "is_bist": "true",
            "is_active": "true",
            "source": "fixture",
            "source_date": "2026-07-01",
        },
        {
            "display_symbol": "KEEP",
            "provider_symbol": "KEEP.IS",
            "name": "Before Name",
            "exchange": "XIST",
            "currency": "TRY",
            "asset_type": "equity",
            "is_bist": "true",
            "is_active": "true",
            "source": "fixture",
            "source_date": "2026-07-01",
        },
    ]
    after = [
        {
            **before[1],
            "name": "After Name",
            "source_date": "2026-07-08",
        },
        {
            **before[0],
            "display_symbol": "NEW",
            "provider_symbol": "NEW.IS",
            "name": "New Company",
            "source_date": "2026-07-08",
        },
    ]
    report = tmp_path / "report.md"

    module["write_refresh_report"](before, after, report, tmp_path / "catalog.csv")

    text = report.read_text(encoding="utf-8")
    assert "- Added: 1" in text
    assert "- Removed / inactive-review needed: 1" in text
    assert "- Changed: 1" in text
    assert "| NEW.IS | NEW | New Company |" in text
    assert "| OLD.IS | OLD | Old Company |" in text
    assert "| KEEP.IS | name | Before Name | After Name |" in text


def test_catalog_refresh_report_includes_provider_validation_failures(tmp_path) -> None:
    module = run_path(str(PROJECT_ROOT / "scripts" / "refresh_bist_symbols.py"))
    report = tmp_path / "report.md"

    module["write_refresh_report"](
        [],
        [],
        report,
        tmp_path / "catalog.csv",
        [
            {
                "provider_symbol": "BAD.IS",
                "status": "failed",
                "failure_kind": "invalid_ticker",
                "error": "invalid ticker",
            }
        ],
    )

    text = report.read_text(encoding="utf-8")
    assert "- Provider validation failures: 1" in text
    assert "| BAD.IS | invalid_ticker | invalid ticker |" in text


def test_catalog_refresh_reads_only_failed_provider_validation_rows(tmp_path) -> None:
    module = run_path(str(PROJECT_ROOT / "scripts" / "refresh_bist_symbols.py"))
    validation = tmp_path / "validation.csv"
    validation.write_text(
        "\n".join(
            (
                "provider_symbol,status,failure_kind,error,candles",
                "GOOD.IS,ok,,,10",
                "BAD.IS,failed,invalid_ticker,invalid ticker,0",
            )
        ),
        encoding="utf-8",
    )

    rows = module["read_provider_failures"](validation)

    assert [row["provider_symbol"] for row in rows] == ["BAD.IS"]


def test_catalog_refresh_stops_before_large_unconfirmed_removal(tmp_path) -> None:
    module = run_path(str(PROJECT_ROOT / "scripts" / "refresh_bist_symbols.py"))
    catalog = tmp_path / "catalog.csv"
    report = tmp_path / "report.md"
    old_rows = [
        {
            "display_symbol": "OLD",
            "provider_symbol": "OLD.IS",
            "name": "Old Company",
            "exchange": "XIST",
            "currency": "TRY",
            "asset_type": "equity",
            "is_bist": "true",
            "is_active": "true",
            "source": "fixture",
            "source_date": "2026-07-01",
        },
        {
            "display_symbol": "KEEP",
            "provider_symbol": "KEEP.IS",
            "name": "Keep Company",
            "exchange": "XIST",
            "currency": "TRY",
            "asset_type": "equity",
            "is_bist": "true",
            "is_active": "true",
            "source": "fixture",
            "source_date": "2026-07-01",
        },
    ]
    module["write_catalog"](old_rows, catalog)
    page = (
        r"\"kapMemberTitle\":\"Keep Company\","
        r"\"stockCode\":\"KEEP\""
    )
    html_path = tmp_path / "kap.html"
    html_path.write_text(page, encoding="utf-8")

    with pytest.raises(SystemExit, match="remove 1 symbols"):
        module["main"](
            [
                "--input-html",
                str(html_path),
                "--output",
                str(catalog),
                "--report",
                str(report),
                "--max-removals-without-confirm",
                "0",
            ]
        )

    with catalog.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert [row["provider_symbol"] for row in rows] == ["OLD.IS", "KEEP.IS"]
    assert "OLD.IS" in report.read_text(encoding="utf-8")


def test_catalog_refresh_allows_confirmed_large_removal(tmp_path) -> None:
    module = run_path(str(PROJECT_ROOT / "scripts" / "refresh_bist_symbols.py"))
    catalog = tmp_path / "catalog.csv"
    report = tmp_path / "report.md"
    module["write_catalog"](
        [
            {
                "display_symbol": "OLD",
                "provider_symbol": "OLD.IS",
                "name": "Old Company",
                "exchange": "XIST",
                "currency": "TRY",
                "asset_type": "equity",
                "is_bist": "true",
                "is_active": "true",
                "source": "fixture",
                "source_date": "2026-07-01",
            }
        ],
        catalog,
    )
    html_path = tmp_path / "kap.html"
    html_path.write_text(
        r"\"kapMemberTitle\":\"New Company\",\"stockCode\":\"NEWC\"",
        encoding="utf-8",
    )

    module["main"](
        [
            "--input-html",
            str(html_path),
            "--output",
            str(catalog),
            "--report",
            str(report),
            "--max-removals-without-confirm",
            "0",
            "--allow-large-removal",
        ]
    )

    with catalog.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert [row["provider_symbol"] for row in rows] == ["NEWC.IS"]


def test_committed_bist_catalog_has_unique_valid_provider_symbols() -> None:
    with CATALOG_PATH.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    provider_symbols = [row["provider_symbol"] for row in rows]
    display_symbols = [row["display_symbol"] for row in rows]

    assert rows
    assert len(provider_symbols) == len(set(provider_symbols))
    assert len(display_symbols) == len(set(display_symbols))
    assert all(symbol.endswith(".IS") for symbol in provider_symbols)
    assert all(row["asset_type"] == "equity" for row in rows)
