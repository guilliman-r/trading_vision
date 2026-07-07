# Drawing persistence

Trading Vision can now persist chart drawings in SQLite. This is a storage layer only; the chart
toolbar and Plotly relayout callback are still tracked as later UI tasks.

Saved drawings are stored in the `drawings` table with:

- `symbol_id` and `interval`, so each chart timeframe can have its own annotations;
- `drawing_type`, such as `line`, `rect`, `circle`, or `path`;
- `shape_json`, the Plotly shape payload exactly as the UI will need it;
- UTC created and updated timestamps.

The `trading_vision.drawing_repository` module provides plain functions to:

- save a new drawing;
- update an existing drawing shape;
- list drawings for a symbol and interval;
- delete one drawing;
- delete all drawings for a symbol, optionally limited to one interval.

Deleting a symbol cascades its drawing rows. Historical candles and pattern results are unaffected.
