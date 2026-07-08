# UI provider request cooldown

Dash can trigger closely spaced callbacks when a user loads a symbol, submits the field, follows a
chart link, or changes an interval. Trading Vision protects Yahoo from identical repeated work with
its durable SQLite candle cache plus a small in-process chart-result cache.

## Behavior

The cache key contains the normalized symbol and interval. BIST display symbols and provider
symbols share a key, so `THYAO` and `THYAO.IS` reuse the same result. Different intervals remain
independent.

An ordinary chart load first uses candles already stored in SQLite. If that symbol and interval have
never been fetched, it calls Yahoo and stores the result. Cached charts retain the normal freshness
label so stale data remains visible, and the status badge says `Cached` rather than implying a new
network response.

The default in-process cooldown is 30 seconds. During that window, a repeated request also reuses
the full chart result, including pattern matches. It does not open another database connection or
rerun detectors.

Concurrent requests for the same key are serialized. The first performs the load; waiting requests
receive that result. Different keys use separate locks and can proceed independently.

## Refresh and expiry

The top-bar **Refresh** button always performs a new provider request, updates SQLite, and replaces
the in-process entry. This explicit action keeps slow provider responses from freezing ordinary
interval changes. If the cached freshness label is stale, use Refresh to request current candles.

Configure the interval in `config.toml`:

```toml
[provider]
cooldown_seconds = 30
```

Allowed values are 0–300 seconds. Set zero to disable only the short-lived chart-result reuse;
SQLite remains the durable candle cache.

## Opt-in live provider test

Normal tests never call Yahoo. To manually check representative BIST and non-BIST symbols against
the live provider, run:

```bash
TV_RUN_LIVE_PROVIDER_TESTS=1 .venv/bin/python -m pytest tests/test_live_provider.py -q
```

Use this sparingly; provider availability, rate limits, and market-data quirks are external to the
local test suite.
