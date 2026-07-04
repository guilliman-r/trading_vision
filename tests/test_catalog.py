from pathlib import Path
from runpy import run_path


def test_kap_catalog_parser_extracts_multiple_stock_codes() -> None:
    module = run_path(str(Path(__file__).parents[1] / "scripts" / "refresh_bist_symbols.py"))
    page = (
        r"\"kapMemberTitle\":\"Example Company\","
        r"\"relatedMemberTitle\":\"Auditor\","
        r"\"stockCode\":\"AAAAB BBBBC BAD\""
    )
    rows = module["parse_companies"](page)
    assert [row["provider_symbol"] for row in rows] == ["AAAAB.IS", "BBBBC.IS"]
