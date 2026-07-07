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

After refreshing, review the generated diff before committing it. Future catalog work will add a
structured report for additions, removals, renames, and provider validation failures.
