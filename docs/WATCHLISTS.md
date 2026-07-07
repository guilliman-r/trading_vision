# Watchlists

Watchlist persistence is intentionally small and local-first.

## Storage

The migration set creates:

- `watchlists`: user-visible lists with a unique name and optional description;
- `watchlist_items`: ordered symbols inside a list, with optional scanner intervals;
- `app_settings`: simple key/value storage for future non-secret user preferences.

Deleting a symbol or watchlist cascades its watchlist item rows. Historical candles, pattern
transitions, and alerts remain separate.

## Repository operations

`trading_vision.watchlist_repository` provides plain functions for:

- creating or updating a watchlist by name;
- listing watchlists;
- adding a symbol to a watchlist;
- listing items in saved order;
- moving an item to a new position;
- removing an item and compacting positions.

Scanner intervals saved on watchlist items are limited to the first supported scanner intervals:
`1d`, `1h`, and `15m`. The experimental `5m` chart interval is not accepted for scanner watchlists.

## UI scope

This milestone adds the persistence layer only. Full watchlist management controls and scan-interval
UI are tracked separately in the roadmap.
