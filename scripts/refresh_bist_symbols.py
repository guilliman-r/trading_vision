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
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "catalogs" / "bist_symbols.csv"
DEFAULT_REPORT = PROJECT_ROOT / "var" / "bist_catalog_refresh_report.md"
DEFAULT_MAX_REMOVALS_WITHOUT_CONFIRM = 20
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
                "asset_type": "equity",
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


def read_catalog(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def catalog_diff(
    before: list[dict[str, str]],
    after: list[dict[str, str]],
) -> dict[str, object]:
    before_by_symbol = {row["provider_symbol"]: row for row in before}
    after_by_symbol = {row["provider_symbol"]: row for row in after}
    before_symbols = set(before_by_symbol)
    after_symbols = set(after_by_symbol)
    added = [after_by_symbol[symbol] for symbol in sorted(after_symbols - before_symbols)]
    removed = [before_by_symbol[symbol] for symbol in sorted(before_symbols - after_symbols)]
    changed = []
    for symbol in sorted(before_symbols & after_symbols):
        field_changes = {
            key: (before_by_symbol[symbol].get(key, ""), after_by_symbol[symbol].get(key, ""))
            for key in sorted(after_by_symbol[symbol])
            if before_by_symbol[symbol].get(key, "") != after_by_symbol[symbol].get(key, "")
            and key != "source_date"
        }
        if field_changes:
            changed.append((symbol, field_changes))
    return {"added": added, "removed": removed, "changed": changed}


def write_refresh_report(
    before: list[dict[str, str]],
    after: list[dict[str, str]],
    report_path: Path,
    output_path: Path,
) -> None:
    diff = catalog_diff(before, after)
    added = diff["added"]
    removed = diff["removed"]
    changed = diff["changed"]
    lines = [
        "# BIST catalog refresh report",
        "",
        f"- Source: {SOURCE_URL}",
        f"- Output CSV: {output_path}",
        f"- Generated: {date.today().isoformat()}",
        f"- Previous rows: {len(before)}",
        f"- New rows: {len(after)}",
        f"- Added: {len(added)}",
        f"- Removed / inactive-review needed: {len(removed)}",
        f"- Changed: {len(changed)}",
        "",
        "Removed symbols are review items. Do not mark many symbols inactive without checking "
        "KAP/BIST.",
        "Provider validation is separate from this catalog scrape.",
        "",
        _rows_section("Added", added),
        _rows_section("Removed / inactive review", removed),
        _changed_section(changed),
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _clean_escaped_text(value: str) -> str:
    value = value.replace(r"\u0026", "&").replace(r"\"", '"')
    return html.unescape(value).strip()


def _rows_section(title: str, rows: list[dict[str, str]]) -> str:
    lines = [f"## {title}", ""]
    if not rows:
        lines.append("None.")
        return "\n".join(lines)
    lines.append("| provider_symbol | display_symbol | name |")
    lines.append("| --- | --- | --- |")
    for row in rows:
        lines.append(
            f"| {row.get('provider_symbol', '')} | {row.get('display_symbol', '')} | "
            f"{row.get('name', '')} |"
        )
    return "\n".join(lines)


def _changed_section(changed) -> str:
    lines = ["## Changed", ""]
    if not changed:
        lines.append("None.")
        return "\n".join(lines)
    lines.append("| provider_symbol | field | before | after |")
    lines.append("| --- | --- | --- | --- |")
    for symbol, field_changes in changed:
        for field, (before, after) in field_changes.items():
            lines.append(f"| {symbol} | {field} | {before} | {after} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-html", type=Path, help="Use a previously downloaded KAP page")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--max-removals-without-confirm",
        type=int,
        default=DEFAULT_MAX_REMOVALS_WITHOUT_CONFIRM,
        help="Stop before writing the CSV when more existing symbols would be removed",
    )
    parser.add_argument(
        "--allow-large-removal",
        action="store_true",
        help="Write the CSV even when removals exceed the review threshold",
    )
    arguments = parser.parse_args(argv)
    page = (
        arguments.input_html.read_text(encoding="utf-8")
        if arguments.input_html
        else download_page()
    )
    before = read_catalog(arguments.output)
    rows = parse_companies(page)
    write_refresh_report(before, rows, arguments.report, arguments.output)
    removed_count = len(catalog_diff(before, rows)["removed"])
    if (
        before
        and removed_count > arguments.max_removals_without_confirm
        and not arguments.allow_large_removal
    ):
        raise SystemExit(
            f"Refresh would remove {removed_count} symbols. Review {arguments.report} and rerun "
            "--allow-large-removal only if this is expected."
        )
    write_catalog(rows, arguments.output)
    print(f"Wrote {len(rows)} KAP codes to {arguments.output}")
    print(f"Wrote refresh report to {arguments.report}")


if __name__ == "__main__":
    main()
