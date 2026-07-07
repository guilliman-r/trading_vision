# Product contract

Trading Vision version 1 is a local, single-user decision-support tool.

## Operating scope

- The application runs on the user's own machine.
- The default server host is `127.0.0.1`.
- Version 1 has no user accounts, roles, passwords, sessions, or remote-access authentication.
- Binding the app to a non-loopback host prints a warning because the UI is unauthenticated.
- SQLite is the local source of persisted candles, patterns, scanner runs, and alerts.

## No order placement

Trading Vision never places trades in version 1. The repository intentionally has no broker
credentials, portfolio order model, order-routing service, or live trading workflow. Pattern alerts
are informational; the user decides whether to act outside the application.

## First scanner intervals

The first supported scanner intervals are:

- `1d`
- `1h`
- `15m`

The chart and provider layers may still load `5m` data manually for investigation, but `5m` is
experimental and is not accepted by scanner configuration or the scanner CLI until performance and
provider limits are measured.

## Closed-candle semantics

Detectors evaluate completed candles by default. A candle becomes eligible only after its full
exchange/provider boundary has passed and the configured provider delay has elapsed.

Examples with the default `provider_delay_seconds = 60`:

- A BIST daily candle is eligible after the exchange data close plus 60 seconds.
- A BIST 15-minute candle opened at `10:15` closes at `10:30` and is eligible at `10:31`.
- Yahoo labels BIST hourly bars on half-hour openings. The `09:30` hourly bar closes at `10:30`
  and is eligible at `10:31`.

If Yahoo includes a still-open BIST bar, the chart may show it as a forming candle, but detectors
ignore it until the completion rule above is satisfied.

## Detector order

The implementation and validation order is:

1. horizontal support/resistance breakouts;
2. double tops and double bottoms;
3. standard and inverse head-and-shoulders;
4. ascending, descending, and symmetrical triangles.

Alerts stay conservative: ambiguous detectors are excluded from default alert rules until their
real-world false-positive behavior is reviewed.

## Initial BIST scan policy

The scanner reads active BIST symbols from SQLite when no explicit symbols are supplied.

The conservative default configuration scans all active BIST symbols on `1d`. The first supported
scan intervals also include `1h` and `15m`, but they must be enabled deliberately in `config.toml`
or supplied to the scanner CLI. Use `15m` on a small explicit symbol set until watchlist controls
and provider throughput measurements are complete.

## Glossary

See [Glossary](GLOSSARY.md) for the domain terms used by detector documentation and scanner output.
