# UI provider request cooldown

Dash can trigger closely spaced callbacks when a user loads a symbol, submits the field, follows a
chart link, or changes an interval. Trading Vision protects Yahoo from identical repeated work with
a small in-process result cache.

## Behavior

The cache key contains the normalized symbol and interval. BIST display symbols and provider
symbols share a key, so `THYAO` and `THYAO.IS` reuse the same result. Different intervals remain
independent.

The default cooldown is 30 seconds. During that window, a repeated request reuses the full chart
load result, including candles, provider status, quality report, and pattern matches. It does not
open another database connection, call Yahoo, or rerun detectors.

Concurrent requests for the same key are serialized. The first performs the load; waiting requests
receive that result. Different keys use separate locks and can proceed independently.

## Refresh and expiry

The top-bar **Refresh** button always performs a new provider request and replaces the cached entry.
After the cooldown expires, the next ordinary request also loads fresh data.

Configure the interval in `config.toml`:

```toml
[provider]
cooldown_seconds = 30
```

Allowed values are 0–300 seconds. Set zero to disable reuse. The cache belongs only to the running
UI process and is intentionally not a second persistence layer; SQLite remains the durable cache.
