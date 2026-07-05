# Symbol search

The chart's symbol field combines a database-backed BIST typeahead with free-form Yahoo Finance
entry. It uses a native browser suggestion list rather than a JavaScript search dependency.

## Suggestions

At application startup, the UI reads every active symbol from SQLite. Each option submits the
short display ticker and shows this label:

```text
THYAO · Türk Hava Yolları
```

The submitted `THYAO` value is resolved by the market-data service to the catalog's `THYAO.IS`
provider symbol. The official company name is stored and displayed unchanged.

If an older generic record and a curated BIST record share a display ticker, the BIST record wins
and the UI shows one option. Inactive records are excluded. Restart or reload the application after
changing the catalog so the startup suggestion snapshot is rebuilt.

## Matching

Repository search checks:

- display ticker, such as `THYAO`;
- provider ticker, such as `THYAO.IS`;
- company name, such as `Türk Hava Yolları`;
- search-only ASCII forms, such as `Turk Hava Yollari`.

Exact display tickers rank first, followed by exact provider tickers, ticker prefixes, and company
names. Turkish characters are normalized only in temporary comparison strings. Catalog values are
never rewritten or stripped of Turkish spelling.

## Symbols outside the catalog

Suggestions are optional. A user may type an arbitrary Yahoo Finance ticker and press Enter or
**Load**. The market-data service stores that ticker as a user-added generic symbol and does not add
`.IS` unless an existing BIST catalog record supplies that mapping.
