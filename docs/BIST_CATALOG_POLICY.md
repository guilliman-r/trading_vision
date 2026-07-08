# BIST catalog policy

Trading Vision's version 1 scan universe targets ordinary Borsa Istanbul equities.

## Included by default

- ordinary listed company shares;
- BIST display symbols mapped to Yahoo Finance provider symbols with the `.IS` suffix;
- active symbols that can be validated by the provider without repeated failure.

## Excluded from the active equity universe

- exchange-traded funds;
- warrants and certificates;
- rights coupons;
- investment funds;
- lease certificates, sukuk, bonds, bills, and other debt instruments;
- broker, bank, factoring, or asset-management member codes that are not ordinary listed shares.

The committed KAP-derived snapshot is treated as a reviewable catalog source, not as proof that
every code is an ordinary equity. Provider validation, inactive marking, additions/removals, and
instrument-class corrections remain explicit catalog-refresh tasks.

## Refresh cadence

Refresh the catalog manually once per month, or sooner after a known BIST listing, delisting,
symbol rename, or provider-mapping issue.

The refresh must not run silently at every application startup. Startup may import the committed
snapshot into SQLite, but catalog changes that add many symbols or mark many inactive symbols
require user review before being applied.

Current manual command:

```bash
.venv/bin/python scripts/refresh_bist_symbols.py
```

After refreshing, review `var/bist_catalog_refresh_report.md` before committing the CSV. The report
lists additions, removed symbols that need inactive-review, and changed fields. Provider validation
is a separate catalog task, so do not treat the scrape report as proof that Yahoo accepts every
symbol.

The refresh script stops before overwriting the CSV when more than 20 existing symbols would be
removed. Review the report first, then rerun with `--allow-large-removal` only when the removal is
expected.

After a catalog refresh, validate provider symbols manually in small batches:

```bash
.venv/bin/python scripts/validate_catalog_provider_symbols.py --max-symbols 25
```

For a full validation run, omit `--max-symbols`. The script writes
`var/bist_provider_validation.csv` with one row per provider symbol, including failure kind and
error text for symbols Yahoo rejects or cannot return.

To include provider failures in the catalog refresh report, rerun the refresh with:

```bash
.venv/bin/python scripts/refresh_bist_symbols.py \
  --provider-validation var/bist_provider_validation.csv
```
