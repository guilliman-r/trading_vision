import csv
from pathlib import Path
from runpy import run_path

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
