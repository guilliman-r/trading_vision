"""Build the BIST symbol snapshot from KAP's official company page."""

from __future__ import annotations

import argparse
import csv
import html
import re
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE_URL = "https://www.kap.org.tr/tr/bist-sirketler"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "catalogs" / "bist_symbols.csv"
ENTRY_PATTERN = re.compile(
    r'\\"kapMemberTitle\\":\\"(?P<name>.*?)\\".*?'
    r'\\"stockCode\\":\\"(?P<codes>.*?)\\"',
)
VALID_CODE = re.compile(r"^[A-Z0-9]{4,6}$")


def download_page() -> str:
    request = Request(SOURCE_URL, headers={"User-Agent": "TradingVision/0.1 personal research"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def parse_companies(page: str) -> list[dict[str, str]]:
    companies: dict[str, dict[str, str]] = {}
    for match in ENTRY_PATTERN.finditer(page):
        name = _clean_escaped_text(match.group("name"))
        codes = _clean_escaped_text(match.group("codes")).split()
        for code in codes:
            if not VALID_CODE.fullmatch(code):
                continue
            companies[code] = {
                "display_symbol": code,
                "provider_symbol": f"{code}.IS",
                "name": name,
                "exchange": "XIST",
                "currency": "TRY",
                "is_bist": "true",
                "is_active": "true",
                "source": SOURCE_URL,
                "source_date": date.today().isoformat(),
            }
    return [companies[code] for code in sorted(companies)]


def write_catalog(rows: list[dict[str, str]], output: Path) -> None:
    if not rows:
        raise ValueError("No company codes were found; KAP's page format may have changed")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _clean_escaped_text(value: str) -> str:
    value = value.replace(r"\u0026", "&").replace(r"\"", '"')
    return html.unescape(value).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-html", type=Path, help="Use a previously downloaded KAP page")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    page = (
        arguments.input_html.read_text(encoding="utf-8")
        if arguments.input_html
        else download_page()
    )
    rows = parse_companies(page)
    write_catalog(rows, arguments.output)
    print(f"Wrote {len(rows)} KAP codes to {arguments.output}")


if __name__ == "__main__":
    main()
