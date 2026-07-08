# Trading Vision — Detailed Implementation Plan

## 1. Product goal

Build a local-first Python application that:

- accepts any symbol supported by Yahoo Finance;
- includes a maintained universe of Borsa Istanbul (BIST) equities by default;
- displays an interactive candlestick chart with familiar TradingView-style controls;
- scans completed candles for chart patterns;
- shows forming and recently confirmed patterns on the chart without stale overlay clutter;
- creates actionable, deduplicated alerts;
- remains intentionally simple to read, test, and modify.

The first release is a decision-support and alerting tool. It does **not** place trades, promise real-time exchange data, or present pattern detections as financial advice.

---

## 2. Product principles

These rules are part of the specification, not optional style preferences.

1. **Prefer obvious code.** Use plain functions, dataclasses, lists, dictionaries, and small classes. Avoid metaprogramming, dependency-injection frameworks, dynamic imports, and clever decorators.
2. **One purpose per module.** A file should have one clear responsibility and a name that describes it.
3. **Keep functions small.** Aim for fewer than 40 lines per function. Split work when a function mixes fetching, transformation, persistence, and presentation.
4. **Keep modules navigable.** Aim for fewer than 300 lines per Python file. Detector modules may exceed this only when keeping one complete pattern definition together is clearer.
5. **Make financial logic inspectable.** Every pattern must have a written definition, named parameters, a reason list, and deterministic tests.
6. **Do not hide failures.** Partial downloads, stale candles, invalid symbols, and notification failures must be visible in the UI and logs.
7. **Store times in UTC.** Convert to `Europe/Istanbul` only for display and exchange-session decisions.
8. **Detect on closed candles by default.** This prevents alerts from appearing and disappearing as the current candle changes.
9. **No future leakage.** A detector may only use candles that existed at the evaluated time.
10. **No premature infrastructure.** Start with SQLite and two Python processes. Add PostgreSQL, Redis, queues, or a separate API only when a measured constraint requires them.
11. **Separate domain logic from UI callbacks.** Detectors and data services must work from tests and the command line without starting Dash.
12. **Make replacement easy.** Yahoo Finance is an adapter, not a dependency embedded throughout the application.

### Code-review checklist

Every change should answer “yes” to these questions:

- Can a new developer locate the relevant code in under two minutes?
- Can the core behavior be explained without knowledge of Dash internals?
- Does a public function have a descriptive name and type hints?
- Is each constant named instead of being a mysterious number in an expression?
- Is financial logic accompanied by a small example or test?
- Are errors either handled or deliberately allowed to propagate with context?
- Does the change avoid a new dependency when the standard library is sufficient?
- Is user-facing behavior covered by an acceptance criterion?

---

## 3. Important constraints and honest expectations

### 3.1 Yahoo Finance is an MVP data source, not an exchange-grade feed

`yfinance` is suitable for personal research and prototyping. Its own documentation states that it is not affiliated with Yahoo, is intended for research and education, and that Yahoo data is intended for personal use. Its download documentation also states that intraday history cannot extend beyond the last 60 days. Therefore:

- do not call the first release “real-time” without measuring actual BIST latency;
- label the UI `Data source: Yahoo Finance` and display the latest candle time;
- treat missing or delayed candles as expected failure modes;
- poll on candle boundaries rather than pretending to consume exchange ticks;
- preserve a provider interface so a licensed BIST feed can replace Yahoo later;
- use a licensed source before relying on the app for time-critical or commercial use.

Useful references:

- [yfinance documentation](https://ranaroussi.github.io/yfinance/)
- [yfinance download parameters and intraday limitation](https://ranaroussi.github.io/yfinance/reference/yfinance.functions.html)
- [Borsa Istanbul licensed data vendors](https://www.borsaistanbul.com/en/data/data-dissemination/data-vendors-directory)

### 3.2 “As patterns happen” needs a precise definition

For this project, it means:

1. download a newly completed candle shortly after the selected interval closes;
2. validate and persist that candle;
3. run enabled detectors using only data available at that moment;
4. update the pattern state;
5. create at most one alert for each meaningful state transition;
6. show when the source data or scanner is stale.

For a 15-minute interval, a normal target is to surface a confirmed pattern within 1–2 minutes of Yahoo making the completed candle available. This is a product target to measure, not a guaranteed feed latency.

### 3.3 Pattern recognition is probabilistic in practice

Traditional chart patterns do not have universally accepted numeric definitions. The app must therefore:

- expose tolerances in settings;
- explain why a match received its score;
- distinguish `forming`, `confirmed`, `invalidated`, and `expired` states;
- allow patterns to be hidden or disabled;
- avoid claiming that a high score predicts profit;
- validate detectors against labeled examples and time-forward evaluation.

### 3.4 BIST coverage needs its own maintained symbol catalog

Borsa Istanbul directs users to the Public Disclosure Platform (KAP) for listed-company information. Yahoo normally represents BIST equities with the `.IS` suffix, but the app should never scatter suffix rules through the code. Maintain a catalog with separate display and provider symbols, for example:

```text
display_symbol = THYAO
provider_symbol = THYAO.IS
exchange = XIST
currency = TRY
```

Reference: [Borsa Istanbul listed companies](https://www.borsaistanbul.com/en/companies/listed-companies).

---

## 4. Recommended first-release architecture

### 4.1 Chosen stack

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.12 | Mature ecosystem support and standard-library `tomllib` |
| UI | Dash | Browser UI driven primarily from Python, with straightforward callbacks |
| Charting | Plotly | Interactive candlesticks, zoom/pan/hover, subplots, annotations, and editable shapes |
| Data frames | pandas | Natural OHLCV manipulation and direct compatibility with `yfinance` |
| Numeric work | NumPy | Transparent vector and rolling calculations without a large TA framework |
| Market data | `yfinance` adapter | Meets the requested MVP source and supports arbitrary Yahoo symbols |
| Storage | SQLite via standard-library `sqlite3` | No server to configure; readable SQL; sufficient for one local user |
| Configuration | TOML + environment overrides | Human-editable local settings without a configuration framework |
| Scanner | Plain long-running Python process | Easy to read and restart; avoids Celery/Redis initially |
| Logging | Standard-library `logging` | Structured enough for local diagnostics without another service |
| Tests | pytest | Simple fixtures and parameterized detector tests |
| Quality | Ruff | One fast tool for formatting and linting |
| Packaging | `pyproject.toml` + virtual environment | Standard Python workflow and editable installation |

Plotly supports programmatic and mouse-drawn lines, rectangles, circles, and paths, and Dash can capture the resulting relayout event. That is enough for the first TradingView-like drawing experience without maintaining a JavaScript front end. See [Plotly shape drawing](https://plotly.com/python/shapes/) and [Dash callbacks](https://dash.plotly.com/basic-callbacks).

### 4.2 Explicitly deferred technology

Do **not** add these to the first release:

- React, Vue, or a separately maintained JavaScript front end;
- FastAPI solely to call Python code from the Python UI;
- Celery, Redis, RabbitMQ, Kafka, or a distributed scheduler;
- PostgreSQL before SQLite concurrency or data volume is measured;
- an ORM before plain SQL becomes a demonstrated burden;
- machine learning before deterministic pattern definitions and labeled data exist;
- Kubernetes or cloud-specific deployment files;
- broker connectivity or automated order placement.

### 4.3 Process model

```text
Browser
   |
   v
Dash UI process ------ reads/writes ------ SQLite database
                                             ^
                                             |
Scanner process ---- fetch/validate/detect --+
       |
       v
yfinance provider adapter
```

Both processes import the same service and detector modules. The UI must not duplicate scanning rules.

### 4.4 Proposed repository layout

```text
trading_vision/
├── README.md
├── IMPLEMENTATION_PLAN.md
├── CHANGELOG.md
├── LICENSE
├── pyproject.toml
├── config.example.toml
├── .env.example
├── .gitignore
├── data/
│   ├── catalogs/
│   │   └── bist_symbols.csv
│   └── fixtures/
│       └── README.md
├── migrations/
│   ├── 001_initial.sql
│   └── 002_add_drawings.sql
├── scripts/
│   ├── refresh_bist_symbols.py
│   ├── backfill.py
│   └── check_data.py
├── trading_vision/
│   ├── __init__.py
│   ├── config.py
│   ├── logging_setup.py
│   ├── models.py
│   ├── database.py
│   ├── repositories.py
│   ├── market_calendar.py
│   ├── data_quality.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── yahoo.py
│   ├── patterns/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── pivots.py
│   │   ├── scoring.py
│   │   ├── double_top.py
│   │   ├── double_bottom.py
│   │   ├── head_shoulders.py
│   │   ├── inverse_head_shoulders.py
│   │   ├── triangles.py
│   │   └── breakouts.py
│   ├── services/
│   │   ├── market_data.py
│   │   ├── pattern_scan.py
│   │   ├── alerts.py
│   │   ├── watchlists.py
│   │   └── drawings.py
│   ├── ui/
│   │   ├── app.py
│   │   ├── layout.py
│   │   ├── chart_builder.py
│   │   ├── callbacks.py
│   │   ├── ids.py
│   │   ├── pages/
│   │   │   ├── chart.py
│   │   │   ├── scanner.py
│   │   │   └── settings.py
│   │   └── assets/
│   │       └── app.css
│   ├── cli.py
│   └── worker.py
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── synthetic/
    │   └── recorded/
    ├── test_config.py
    ├── test_database.py
    ├── test_data_quality.py
    ├── test_yahoo_provider.py
    ├── test_pivots.py
    ├── test_patterns.py
    ├── test_pattern_states.py
    ├── test_scanner.py
    └── test_ui_smoke.py
```

This is a target layout, not a requirement to create empty placeholder modules. Add a file only when its first behavior is implemented.

---

## 5. Domain language and data contracts

Agree on these terms before detector implementation.

### 5.1 Candle

A time-bounded OHLCV record:

- `symbol_id`
- `interval`
- `opened_at_utc`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `is_complete`
- `is_adjusted`
- `source`
- `fetched_at_utc`

Validation rules:

- `high >= max(open, close, low)`;
- `low <= min(open, close, high)`;
- all prices are positive;
- volume is null or non-negative;
- timestamps are timezone-aware before persistence;
- only one candle exists for `(symbol, interval, opened_at_utc)`;
- detector input is strictly sorted and contains no duplicate timestamps.

### 5.2 Pivot

A locally significant high or low confirmed by a configurable number of candles on both sides.

Fields:

- timestamp and candle index;
- price;
- kind: `high` or `low`;
- left/right confirmation window;
- prominence measured in percent and ATR units.

Important: a pivot using three candles to the right becomes knowable only after those three candles close. Store its `confirmed_at` time separately from the pivot candle time.

### 5.3 Pattern candidate

A geometric formation that meets structural rules but has not yet crossed its confirmation boundary.

### 5.4 Confirmed pattern

A candidate whose breakout or breakdown rule was satisfied by a completed candle. Confirmation must specify:

- boundary price;
- confirming candle time and close;
- breakout buffer;
- whether volume confirmation passed;
- target estimate;
- invalidation level;
- transparent score and reasons.

### 5.5 Pattern state

Use only these states initially:

- `forming`: geometry matches, no breakout yet;
- `confirmed`: a completed candle crossed the confirmation boundary;
- `invalidated`: price violated the structure before or after confirmation;
- `expired`: no confirmation within the allowed number of candles.

Do not overload states with alert delivery status.

### 5.6 Alert event

An immutable record that a pattern changed state or crossed a user rule. A separate delivery record tracks whether each in-app or explicitly selected external notification succeeded.

---

## 6. Database design

Use readable SQL migration files and repository functions. Enable SQLite WAL mode, foreign keys, and a busy timeout on every connection.

### 6.1 Tables for the first useful release

#### `symbols`

- `id` integer primary key
- `display_symbol` text
- `provider_symbol` text unique
- `name` text nullable
- `exchange` text nullable
- `currency` text nullable
- `asset_type` text nullable
- `is_bist` integer boolean
- `is_active` integer boolean
- `last_validated_at` text nullable
- `metadata_json` text nullable

Indexes:

- unique index on normalized `provider_symbol`;
- index on `(is_bist, is_active)`;
- index on normalized `display_symbol`.

#### `candles`

- `symbol_id` foreign key
- `interval` text
- `opened_at_utc` text
- `open`, `high`, `low`, `close` real
- `volume` real nullable
- `is_complete` integer boolean
- `is_adjusted` integer boolean
- `source` text
- `fetched_at_utc` text

Primary key: `(symbol_id, interval, opened_at_utc)`.

Indexes:

- `(symbol_id, interval, opened_at_utc desc)` for chart loading;
- `(interval, opened_at_utc desc)` for scanner diagnostics.

#### `patterns`

- `id` text primary key, generated from a stable fingerprint
- `symbol_id` foreign key
- `interval` text
- `pattern_type` text
- `direction` text
- `state` text
- `started_at_utc` text
- `ended_at_utc` text nullable
- `confirmed_at_utc` text nullable
- `score` real
- `boundary_price` real nullable
- `target_price` real nullable
- `invalidation_price` real nullable
- `points_json` text
- `reasons_json` text
- `parameters_json` text
- `detector_version` text
- `first_seen_at_utc` text
- `last_seen_at_utc` text

Indexes:

- `(symbol_id, interval, state, last_seen_at_utc desc)`;
- `(state, pattern_type, confirmed_at_utc desc)` for the scanner feed.

#### `pattern_transitions`

- `id` integer primary key
- `pattern_id` foreign key
- `old_state` text nullable
- `new_state` text
- `changed_at_utc` text
- `reason` text

This preserves an audit trail instead of overwriting all history in `patterns`.

#### `scan_runs`

- `id` integer primary key
- `started_at_utc`
- `finished_at_utc` nullable
- `interval`
- `symbols_requested`
- `symbols_succeeded`
- `symbols_failed`
- `candles_added`
- `patterns_added`
- `status`
- `error_summary` nullable

#### `watchlists` and `watchlist_items`

- keep a default BIST watchlist and one user-created watchlist;
- preserve item ordering;
- store enabled scan intervals per item or in a small JSON field initially.

#### `alert_rules`

- `id`
- optional symbol, interval, and pattern type filters;
- minimum score;
- allowed states;
- enabled delivery channels;
- active flag.

#### `alert_events`

- immutable matched rule and pattern transition;
- unique fingerprint to prevent duplicates;
- created and acknowledged timestamps.

#### `notification_deliveries`

- one row per alert and channel;
- status, attempt count, last error, delivered timestamp.

#### `drawings`

- symbol, interval, drawing type, Plotly shape JSON, created/updated timestamps.

#### `app_settings`

- simple key/value table for non-secret user preferences.

### 6.2 Data retention defaults

- Daily candles: retain indefinitely.
- Hourly candles: retain indefinitely initially; review database size quarterly.
- 15-minute candles: retain at least the 60-day source window and optionally archive longer locally.
- 5-minute candles: default to watchlist symbols only; retain 60 days initially.
- Scan runs: retain 90 days.
- Pattern transitions and alert events: retain indefinitely unless the user clears them.

---

## 7. Pattern engine design

### 7.1 Detector interface

Keep the interface concrete and boring:

```python
def detect_double_tops(
    candles: pd.DataFrame,
    settings: DoubleTopSettings,
) -> list[PatternMatch]:
    """Return every knowable double-top match in chronological order."""
```

Each detector receives a clean candle frame plus a typed settings object and returns data. It must not:

- access the database;
- download data;
- send alerts;
- read Dash state;
- use the current wall-clock time implicitly;
- mutate the caller's DataFrame.

### 7.2 Shared calculations

Implement and test these once:

- true range and ATR;
- percent distance;
- linear slope using an explicit least-squares formula or `numpy.polyfit` with a short explanatory wrapper;
- local pivot extraction;
- pivot alternation cleanup;
- line value at a candle index;
- breakout/breakdown test;
- volume ratio against rolling median;
- stable pattern fingerprint;
- score clamping and reason formatting.

Avoid importing a large technical-analysis package just to calculate a small number of formulas.

### 7.3 Transparent scoring

Use a 0–100 score as a quality description, not a probability. A suggested first formula:

| Component | Maximum points |
|---|---:|
| Geometry and symmetry | 35 |
| Pivot prominence | 20 |
| Pattern duration | 10 |
| Boundary quality/touches | 15 |
| Breakout strength | 10 |
| Relative volume | 10 |

Every awarded or deducted component must produce a reason, such as:

```text
+28 peaks are 0.7% apart (limit 2.0%)
+16 both peaks exceed 1.2 ATR prominence
+10 close finished 0.6 ATR below neckline
-5 breakout volume was below its 20-bar median
```

The score must be reproducible from stored detector parameters.

### 7.4 Pattern definitions for the MVP

#### A. Support/resistance breakout

Purpose: validate the full pipeline with the simplest useful signal.

Rules:

- identify a level from at least two confirmed pivots;
- require touches within a configurable ATR or percentage tolerance;
- require a completed candle close outside the level plus breakout buffer;
- optionally require volume above a rolling median multiple;
- invalidate if the next configured number of closes return decisively through the level;
- target is optional and should not affect detection.

#### B. Double top

Rules:

- pivot sequence is high → low → high;
- both highs are prominent;
- peak prices are within `peak_tolerance`;
- trough depth exceeds minimum percent or ATR depth;
- duration is within configured minimum/maximum bars;
- forming state begins after the second high is confirmed;
- confirmation occurs when a completed candle closes below the trough neckline plus buffer;
- invalidation occurs when price closes above the higher peak plus buffer before confirmation;
- measured target is neckline minus pattern height.

#### C. Double bottom

Mirror the double-top rules, but implement it in a separate readable function rather than a difficult sign-flipping abstraction. Shared low-level helpers are acceptable.

#### D. Head and shoulders

Rules:

- pivot sequence is high → low → higher high → low → lower/equal high;
- head is higher than both shoulders by a configured minimum;
- shoulders are within a configured price tolerance;
- time spacing is reasonably symmetric;
- neckline is fitted through the two intervening lows;
- reject necklines with implausible slopes;
- confirm on a completed close below the neckline plus buffer;
- target is breakout neckline value minus head-to-neckline height.

#### E. Inverse head and shoulders

Implement as its own readable detector using mirrored domain terms and tests.

#### F. Triangles

Start only after the preceding detectors are stable.

- Ascending: approximately flat resistance plus rising support.
- Descending: falling resistance plus approximately flat support.
- Symmetrical: falling resistance plus rising support.
- Require at least two touches on each side.
- Fit boundaries only from confirmed pivots.
- Require converging lines and an apex later than the final formation point.
- Reject patterns that are too short, too wide, or have already passed the apex.
- Confirm only on a completed close outside the relevant boundary plus buffer.

### 7.5 Patterns deferred until after validation

- flags and pennants;
- wedges;
- cup and handle;
- rounding tops/bottoms;
- harmonic patterns;
- candlestick patterns;
- learned or image-based recognition.

These can produce many ambiguous matches. Add them only with definitions, examples, and a user need.

### 7.6 Deduplication

Build a stable fingerprint from:

- provider symbol;
- interval;
- pattern type;
- rounded timestamps of defining pivots;
- detector major version.

Updating `forming` to `confirmed` must update the same pattern and append a state transition. Small score changes must not create new alerts.

---

## 8. User experience specification

### 8.1 Main chart page

#### Top bar

- product name;
- searchable symbol selector;
- interval selector: `1d`, `1h`, `15m`, then `5m` after performance validation;
- visible data-source label;
- last candle time;
- scanner status dot;
- light/dark theme toggle;
- settings link.

#### Left panel

- watchlist selector;
- filterable symbol list;
- latest price and daily change;
- small badges for new forming/confirmed patterns;
- stale-data warning per symbol;
- button to add any Yahoo ticker.

#### Center chart

- candlestick trace;
- volume subplot;
- zoom, pan, autoscale, and reset;
- crosshair-like spike lines and hover data;
- optional moving averages only after the core chart works;
- colored lines/polygons for detected patterns;
- markers at defining pivots;
- neckline/boundary, target, and invalidation lines;
- drawing tools for line, rectangle, circle, path, and erase;
- legend controls to show/hide individual overlay categories;
- preserve zoom while new data is appended.

#### Right panel

- selected pattern name and state;
- plain-language explanation;
- score breakdown;
- start and confirmation times;
- boundary, target, and invalidation prices;
- source freshness;
- acknowledge/mute alert controls;
- next/previous pattern navigation.

#### Empty and error states

- invalid symbol: show the provider error and keep the previous chart;
- no data: show suggested symbol-format examples;
- no pattern: state this plainly rather than displaying an empty panel;
- stale data: show last successful fetch and last error;
- scanner stopped: link to start instructions;
- partial BIST download: state how many symbols succeeded and failed.

### 8.2 Scanner page

- table of current forming and newly confirmed patterns;
- filters for symbol, watchlist, interval, type, state, direction, score, and age;
- sortable confirmation time and score;
- colored but accessible state badges;
- click a row to open the chart at that pattern;
- show pattern reasons without opening source code;
- acknowledge alerts individually or in bulk;
- export filtered results as CSV;
- show scan health summary and failed symbols.

### 8.3 Settings page

- data refresh intervals;
- enabled chart intervals;
- enabled detector list;
- detector parameter groups with descriptions and reset buttons;
- minimum alert score;
- volume confirmation toggle;
- scan universe: all BIST or selected watchlists;
- retention settings;
- theme and timezone;
- notification channel setup;
- diagnostic “test data source” and “test notification” actions.

### 8.4 Responsive scope

- Optimize version 1 for desktop widths of 1280px and above.
- Keep the chart usable on tablets.
- On narrow screens, collapse left and right panels into drawers.
- Do not attempt pixel-for-pixel TradingView imitation.
- Add keyboard navigation and visible focus styles for controls.

---

## 9. Detailed phased backlog

Priorities:

- **P0:** required for the first useful release;
- **P1:** required for a dependable personal release;
- **P2:** valuable later, after measured use.

Sizes are relative: **XS** (under half a day), **S** (about half to one day), **M** (one to three days), **L** (several days with validation). They are planning aids, not commitments.

### Phase 0 — Confirm the product contract

- [x] **TV-0001 — P0 / XS:** Record that version 1 is local and single-user.
  - Acceptance: README states who runs it, where it runs, and that authentication is absent.
- [x] **TV-0002 — P0 / XS:** Define the first scan intervals as `1d`, `1h`, and `15m`.
  - Acceptance: config validates only supported values; `5m` is explicitly experimental/deferred.
- [x] **TV-0003 — P0 / XS:** Define “closed candle” semantics for every interval.
  - Acceptance: one written example shows when a 15-minute candle is eligible for detection.
- [x] **TV-0004 — P0 / XS:** Choose initial detector order: breakout, double top/bottom, head-and-shoulders, triangles.
  - Acceptance: backlog and settings use the same names.
- [x] **TV-0005 — P0 / XS:** Set the initial BIST scan policy.
  - Default: all active BIST equities on `1d` and `1h`; user watchlist on `15m`.
  - Acceptance: the policy is configurable and visible in settings.
- [x] **TV-0006 — P0 / XS:** State that the app never places orders.
  - Acceptance: no broker credentials or order models exist in version 1.
- [x] **TV-0007 — P0 / XS:** Write a one-page glossary for candle, pivot, candidate, confirmation, invalidation, and alert.
  - Acceptance: detector docs use these terms consistently.

**Exit criterion:** product boundaries and default behavior are unambiguous.

### Phase 1 — Repository and developer experience

- [x] **TV-0101 — P0 / XS:** Initialize Git with `main` as the default branch.
- [x] **TV-0102 — P0 / XS:** Add a Python-focused `.gitignore` covering virtual environments, caches, databases, logs, and editor files.
- [x] **TV-0103 — P0 / S:** Create `pyproject.toml` with package metadata and separate runtime/dev dependency groups.
- [x] **TV-0104 — P0 / XS:** Pin Python compatibility to `>=3.12,<3.14` initially and document how to revisit it.
- [x] **TV-0105 — P0 / XS:** Add install commands using standard `python -m venv` and `python -m pip`.
- [x] **TV-0106 — P0 / XS:** Configure Ruff with a small, documented rule set; avoid dozens of stylistic exceptions.
- [x] **TV-0107 — P0 / XS:** Configure pytest and a temporary database fixture.
- [x] **TV-0108 — P0 / XS:** Add `README.md` sections: purpose, limitations, install, run UI, run scanner, test, and troubleshoot.
- [x] **TV-0109 — P0 / XS:** Add `config.example.toml` with every setting commented in plain language.
- [x] **TV-0110 — P0 / XS:** Add `.env.example` only for secrets such as notification tokens.
- [x] **TV-0111 — P1 / S:** Add a CI workflow that installs, runs Ruff, and executes tests on one supported Python version.
- [x] **TV-0112 — P1 / XS:** Add a pull-request checklist based on the project principles.
- [x] **TV-0113 — P1 / XS:** Add `CHANGELOG.md` and use simple semantic versioning.
- [x] **TV-0114 — P1 / XS:** Choose and add an appropriate project license.

**Exit criterion:** a new machine can install and run an empty smoke-test application from written instructions.

### Phase 2 — Configuration, logging, and core models

- [x] **TV-0201 — P0 / S:** Implement a `Settings` dataclass with explicit defaults.
- [x] **TV-0202 — P0 / S:** Load optional TOML configuration with `tomllib`.
- [x] **TV-0203 — P0 / S:** Support a short documented list of environment overrides for paths and secrets.
- [x] **TV-0204 — P0 / XS:** Validate intervals, timezones, positive polling values, and score ranges at startup.
- [x] **TV-0205 — P0 / S:** Implement standard logging configuration for console and rotating local file output.
- [x] **TV-0206 — P0 / XS:** Give UI and scanner logs a process name and scan-run identifier.
- [x] **TV-0207 — P0 / S:** Create typed models for `Symbol`, `Candle`, `Pivot`, `PatternMatch`, and `AlertEvent`.
- [x] **TV-0208 — P0 / XS:** Keep models free of database and UI methods.
- [x] **TV-0209 — P0 / S:** Add unit tests for valid/invalid settings and model construction.
- [x] **TV-0210 — P1 / XS:** Add a command that prints effective non-secret configuration.

**Exit criterion:** all processes use one validated configuration model and consistent logging.

### Phase 3 — SQLite schema and repositories

- [x] **TV-0301 — P0 / S:** Add a database connection helper that enables foreign keys, WAL mode, row objects, and busy timeout.
- [x] **TV-0302 — P0 / M:** Write `001_initial.sql` for symbols, candles, patterns, transitions, scan runs, watchlists, alerts, and settings.
- [x] **TV-0303 — P0 / S:** Implement a tiny migration runner with a `schema_migrations` table.
- [x] **TV-0304 — P0 / S:** Implement symbol upsert, get, search, list-active, and mark-inactive functions.
- [x] **TV-0305 — P0 / M:** Implement bulk candle upsert in a transaction.
- [x] **TV-0306 — P0 / S:** Implement candle range and latest-candle queries.
- [x] **TV-0307 — P0 / M:** Implement pattern upsert and immutable transition append in one transaction.
- [x] **TV-0308 — P0 / S:** Implement scan-run start/finish/fail operations.
- [x] **TV-0309 — P0 / S:** Implement watchlist create, reorder, add, and remove operations.
- [x] **TV-0310 — P0 / M:** Implement alert rule/event queries and unique deduplication fingerprints.
- [x] **TV-0311 — P1 / S:** Implement drawings save/load/delete operations.
- [x] **TV-0312 — P0 / M:** Test every repository against a fresh temporary database.
- [x] **TV-0313 — P0 / S:** Test migration idempotency and upgrade from each committed schema fixture.
- [x] **TV-0314 — P1 / S:** Add a database backup command using SQLite's backup API.
- [x] **TV-0315 — P1 / XS:** Add a command that prints table counts and database size.

**Exit criterion:** persistence is deterministic, migration-driven, and fully testable without network access.

### Phase 4 — BIST symbol catalog

- [x] **TV-0401 — P0 / S:** Define CSV columns for display symbol, provider symbol, company name, exchange, currency, asset type, active flag, and source date.
- [ ] **TV-0402 — P0 / M:** Obtain the initial active-equity list from Borsa Istanbul/KAP and store a versioned snapshot.
- [x] **TV-0403 — P0 / S:** Explicitly decide whether ETFs, warrants, rights, and investment funds are excluded.
  - Default: include ordinary listed equities; exclude non-equity instruments.
- [x] **TV-0404 — P0 / S:** Normalize Turkish characters only in search aliases, never by damaging official company names.
- [x] **TV-0405 — P0 / S:** Map BIST display symbols to Yahoo `.IS` provider symbols in the catalog builder.
- [ ] **TV-0406 — P0 / M:** Validate catalog provider symbols in rate-limited batches and record failures.
- [x] **TV-0407 — P0 / S:** Import the snapshot into `symbols` on first run.
- [x] **TV-0408 — P0 / S:** Build symbol search across exact ticker, provider ticker, company name, and aliases.
- [ ] **TV-0409 — P1 / M:** Implement a manual refresh script that downloads/reads the official source and generates a diff.
- [ ] **TV-0410 — P1 / S:** Require user review before catalog changes mark many symbols inactive.
- [ ] **TV-0411 — P1 / S:** Record additions, removals, renames, and provider failures in a refresh report.
- [x] **TV-0412 — P1 / S:** Schedule a monthly reminder or documented manual catalog refresh—not an opaque scrape at every startup.
- [x] **TV-0413 — P0 / M:** Add tests for `.IS` mapping, duplicate detection, invalid rows, and inactive symbols.

**Exit criterion:** all intended BIST equities are searchable, and catalog provenance is visible.

### Phase 5 — Provider boundary and Yahoo data ingestion

- [x] **TV-0501 — P0 / S:** Define a small `MarketDataProvider` interface: validate symbol, fetch bars, and fetch lightweight metadata.
- [x] **TV-0502 — P0 / S:** Define a result object that carries successful data and per-symbol errors together.
- [x] **TV-0503 — P0 / M:** Implement Yahoo single-symbol history fetch with every important argument explicit.
- [x] **TV-0504 — P0 / M:** Implement batched multi-symbol downloads with a configurable batch size.
- [x] **TV-0505 — P0 / S:** Normalize Yahoo's single- and multi-ticker column shapes into one internal schema.
- [x] **TV-0506 — P0 / S:** Convert provider timestamps to UTC and retain exchange metadata separately.
- [x] **TV-0507 — P0 / XS:** Choose adjusted-price behavior explicitly rather than accepting a changing library default.
  - Default: use adjusted OHLC for pattern continuity and record `is_adjusted=True`.
- [x] **TV-0508 — P0 / S:** Remove or flag the still-open candle based on interval and exchange session.
- [x] **TV-0509 — P0 / M:** Implement bounded retries with exponential backoff and random jitter.
- [x] **TV-0510 — P0 / S:** Treat invalid ticker, empty history, rate limiting, timeout, and partial batch failure separately.
- [x] **TV-0511 — P0 / S:** Log request duration and returned candle range without logging secrets.
- [x] **TV-0512 — P0 / S:** Add a small in-process cooldown to avoid repeated identical requests from UI callbacks.
- [x] **TV-0513 — P0 / M:** Upsert only new/changed candles and report added/updated counts.
- [x] **TV-0514 — P0 / S:** Add a generic Yahoo symbol through the UI without appending `.IS` unless it matches the BIST catalog.
- [x] **TV-0515 — P0 / S:** Add frozen provider-shape tests so most tests never contact Yahoo.
- [ ] **TV-0516 — P1 / M:** Add a manually invoked live integration test for representative BIST and non-BIST symbols.
- [x] **TV-0517 — P1 / S:** Capture the installed `yfinance` version in diagnostic output.
- [x] **TV-0518 — P1 / S:** Add a provider health result showing success rate, latency, and latest returned bar age.

**Exit criterion:** `THYAO.IS` and a non-BIST Yahoo ticker can be fetched, normalized, validated, stored, and diagnosed.

### Phase 6 — Market calendar and data quality

- [x] **TV-0601 — P0 / S:** Represent interval lengths and expected candle boundaries in one module.
- [x] **TV-0602 — P0 / M:** Implement BIST session awareness using official trading hours and holiday data that can be updated without code changes.
- [x] **TV-0603 — P0 / S:** Handle half days and exceptional closures through a small override data file.
- [x] **TV-0604 — P0 / S:** Define when daily candles become eligible for scanning.
- [x] **TV-0605 — P0 / M:** Validate OHLC relationships, positive prices, non-negative volume, duplicates, ordering, and timezone awareness.
- [x] **TV-0606 — P0 / S:** Detect gaps relative to expected session candles without inventing missing prices.
- [x] **TV-0607 — P0 / S:** Define stale thresholds per interval.
- [x] **TV-0608 — P0 / S:** Distinguish “market closed” from “feed stale.”
- [x] **TV-0609 — P0 / S:** Quarantine invalid rows and preserve an error summary instead of silently dropping them.
- [ ] **TV-0610 — P1 / M:** Detect suspicious split-like jumps and compare them with corporate-action information.
- [x] **TV-0611 — P0 / M:** Create fixture tests for DST boundaries, weekends, holidays, half days, duplicates, and malformed OHLC.
- [x] **TV-0612 — P1 / S:** Build `scripts/check_data.py` to print coverage and quality by symbol/interval.

**Exit criterion:** scanners cannot unknowingly run on partial, malformed, or obviously stale data.

### Phase 7 — First interactive chart

- [x] **TV-0701 — P0 / S:** Create the Dash app factory without fetching network data at import time.
- [x] **TV-0702 — P0 / S:** Build a page shell with top bar, left panel, chart area, and right details panel.
- [x] **TV-0703 — P0 / S:** Add a dark theme using one readable CSS file and CSS variables.
- [x] **TV-0704 — P0 / S:** Populate the symbol selector from the database.
- [x] **TV-0705 — P0 / XS:** Add the interval selector and validate supported combinations.
- [ ] **TV-0706 — P0 / M:** Build a pure `build_chart(candles, patterns, drawings, options)` function.
- [x] **TV-0707 — P0 / S:** Add candlesticks and a synchronized volume subplot.
- [x] **TV-0708 — P0 / S:** Configure range breaks so closed-market gaps are understandable.
- [x] **TV-0709 — P0 / S:** Add hover details for timestamp, OHLC, absolute change, percent change, and volume.
- [x] **TV-0710 — P0 / S:** Add zoom, pan, autoscale, reset, and image export controls.
- [x] **TV-0711 — P0 / S:** Add spike lines/crosshair behavior supported by Plotly.
- [x] **TV-0712 — P0 / S:** Show latest-candle timestamp, source, and stale state above the chart.
- [x] **TV-0713 — P0 / S:** Keep network loading out of the chart builder.
- [x] **TV-0714 — P0 / S:** Preserve user zoom with stable `uirevision` values.
- [x] **TV-0715 — P0 / S:** Add loading, invalid-symbol, no-data, and provider-error states.
- [ ] **TV-0716 — P1 / M:** Enable drawing tools and persist relayout shape changes.
- [ ] **TV-0717 — P1 / S:** Add show/hide and delete-all controls for user drawings.
- [ ] **TV-0718 — P1 / M:** Make panels collapsible and usable at tablet width.
- [x] **TV-0719 — P0 / M:** Add smoke tests for app creation and chart construction from fixed candles.
- [x] **TV-0720 — P0 / S:** Limit live overlays to forming/recent confirmed patterns and scale the
  default viewport from visible candle prices rather than projected geometry.

**Exit criterion:** a user can search a symbol, switch interval, inspect candlesticks/volume, zoom, and understand data freshness.

### Phase 8 — Shared pivot and scoring foundation

- [x] **TV-0801 — P0 / S:** Implement true range and ATR with formula comments and tests.
- [x] **TV-0802 — P0 / M:** Implement confirmed local-high/local-low pivot extraction.
- [x] **TV-0803 — P0 / S:** Record both pivot time and knowledge/confirmation time.
- [x] **TV-0804 — P0 / S:** Remove adjacent same-kind pivots by retaining the more extreme one.
- [x] **TV-0805 — P0 / S:** Calculate percent and ATR prominence.
- [x] **TV-0806 — P0 / S:** Implement line fitting/value helpers and explain input units.
- [x] **TV-0807 — P0 / S:** Implement breakout/breakdown tests on completed closes.
- [x] **TV-0808 — P0 / S:** Implement rolling median volume ratio with null/zero handling.
- [x] **TV-0809 — P0 / M:** Implement score components and human-readable reasons.
- [x] **TV-0810 — P0 / S:** Implement stable fingerprints.
- [x] **TV-0811 — P0 / M:** Generate synthetic trend, range, and noise fixtures.
- [x] **TV-0812 — P0 / M:** Prove in tests that truncating future candles does not alter already knowable pivots.
- [x] **TV-0813 — P0 / S:** Benchmark pivot extraction over the maximum planned candle window.

**Exit criterion:** every later detector can reuse a leak-free, documented pivot representation.

### Phase 9 — Breakout detector vertical slice

- [x] **TV-0901 — P0 / S:** Define breakout settings with names, units, defaults, and allowed ranges.
- [x] **TV-0902 — P0 / M:** Detect repeated horizontal resistance and support levels.
- [x] **TV-0903 — P0 / S:** Require minimum touch count and spacing.
- [x] **TV-0904 — P0 / S:** Implement forming, confirmed, invalidated, and expired transitions.
- [x] **TV-0905 — P0 / S:** Score geometry, touches, breakout strength, and volume.
- [x] **TV-0906 — P0 / S:** Persist matches and transitions with stable IDs.
- [x] **TV-0907 — P0 / S:** Render level, touch pivots, confirmation marker, target, and invalidation.
- [x] **TV-0908 — P0 / S:** Show score reasons in the detail panel.
- [x] **TV-0909 — P0 / M:** Add positive, negative, edge, and no-future-leakage tests.
- [x] **TV-0910 — P0 / M:** Run a manual scan on a small fixed BIST watchlist and review every match.

**Exit criterion:** one complete signal travels from downloaded candle to UI explanation without manual database edits.

### Phase 10 — Double top and double bottom

- [x] **TV-1001 — P0 / S:** Write detector definitions and diagrams in developer documentation.
- [x] **TV-1002 — P0 / M:** Implement double-top candidate geometry.
- [x] **TV-1003 — P0 / S:** Implement neckline confirmation and pre-confirmation invalidation.
- [x] **TV-1004 — P0 / S:** Implement measured target calculation.
- [x] **TV-1005 — P0 / S:** Implement score and reasons.
- [x] **TV-1006 — P0 / M:** Implement double-bottom logic with mirrored domain wording.
- [x] **TV-1007 — P0 / S:** Add overlay builders for peaks/troughs, neckline, breakout, target, and invalidation.
- [x] **TV-1008 — P0 / M:** Add hand-built perfect, imperfect, too-shallow, too-wide, and false-break fixtures.
- [x] **TV-1009 — P0 / M:** Add time-forward tests that reveal exactly when a candidate and confirmation become knowable.
- [ ] **TV-1010 — P0 / M:** Review results on frozen real BIST examples and record false positives.
- [ ] **TV-1011 — P1 / S:** Add per-detector settings UI with reset-to-default.

**Exit criterion:** both patterns have deterministic state timing and understandable chart overlays.

### Phase 11 — Head-and-shoulders family

- [x] **TV-1101 — P0 / S:** Document shoulder equality, head prominence, timing symmetry, and neckline-slope limits.
- [x] **TV-1102 — P0 / L:** Implement head-and-shoulders candidate generation from alternating pivots.
- [x] **TV-1103 — P0 / M:** Fit and evaluate a sloped neckline.
- [x] **TV-1104 — P0 / S:** Confirm, invalidate, expire, and calculate target.
- [x] **TV-1105 — P0 / S:** Add component score and reasons.
- [x] **TV-1106 — P0 / L:** Implement inverse head-and-shoulders separately.
- [x] **TV-1107 — P0 / M:** Render shoulders, head, neckline, confirmation, target, and invalidation.
- [ ] **TV-1108 — P0 / L:** Add synthetic and frozen-real positive/negative fixtures.
- [x] **TV-1109 — P0 / M:** Add tests for steep neckline rejection and asymmetric shoulders.
- [ ] **TV-1110 — P0 / M:** Manually label and review a representative BIST sample before enabling alerts by default.

**Exit criterion:** detectors are enabled only after their false-positive behavior has been inspected.

### Phase 12 — Triangle family

- [x] **TV-1201 — P1 / S:** Document flat-line tolerance, convergence, touch count, duration, and apex rules.
- [x] **TV-1202 — P1 / M:** Build separate high- and low-pivot line fits.
- [x] **TV-1203 — P1 / M:** Implement ascending-triangle classification.
- [x] **TV-1204 — P1 / M:** Implement descending-triangle classification.
- [x] **TV-1205 — P1 / M:** Implement symmetrical-triangle classification.
- [x] **TV-1206 — P1 / S:** Reject parallel, diverging, passed-apex, and insufficient-touch structures.
- [x] **TV-1207 — P1 / M:** Implement direction-aware confirmations and invalidations.
- [x] **TV-1208 — P1 / S:** Add score reasons and target estimates.
- [x] **TV-1209 — P1 / M:** Render both boundaries, touch points, apex, confirmation, and target.
- [ ] **TV-1210 — P1 / L:** Build synthetic and real fixtures for each class and common false positive.

**Exit criterion:** triangle labels are stable under small data extensions and do not classify ordinary channels as triangles.

### Phase 13 — Scanner process

- [x] **TV-1301 — P0 / S:** Implement `python -m trading_vision.worker` with graceful Ctrl-C shutdown.
- [x] **TV-1302 — P0 / S:** Acquire a simple process lock so two local scanners do not run accidentally.
- [x] **TV-1303 — P0 / M:** Calculate which symbol/interval jobs are due from the last completed candle.
- [x] **TV-1304 — P0 / M:** Batch due symbols by interval and provider.
- [x] **TV-1305 — P0 / M:** Fetch, quality-check, store, detect, and persist in explicit sequential steps.
- [x] **TV-1306 — P0 / S:** Isolate per-batch/per-symbol failures so one bad ticker does not abort the full run.
- [x] **TV-1307 — P0 / S:** Persist scan-run counts and concise errors.
- [x] **TV-1308 — P0 / S:** Sleep only until the next relevant boundary, with a configurable provider delay.
- [x] **TV-1309 — P0 / S:** Avoid polling closed markets except for daily/catch-up jobs.
- [x] **TV-1310 — P0 / S:** Catch up missing candles after restart before scanning.
- [x] **TV-1311 — P0 / S:** Scan only a bounded lookback window required by the enabled detectors.
- [x] **TV-1312 — P0 / S:** Emit a heartbeat row or timestamp visible to the UI.
- [x] **TV-1313 — P0 / M:** Add an end-to-end worker test using a fake provider and temporary database.
- [x] **TV-1314 — P1 / M:** Add a one-shot mode for manual runs and scheduled environments.
- [x] **TV-1315 — P1 / S:** Add a dry-run mode that downloads/detects but does not create alerts.
- [ ] **TV-1316 — P1 / M:** Measure full-universe duration by interval and tune only after collecting numbers.

**Exit criterion:** the scanner can run unattended, recover after restart, and clearly report partial failure.

### Phase 14 — Alert rules and notification center

- [x] **TV-1401 — P0 / S:** Create one default rule: newly confirmed enabled patterns above a configurable score.
- [x] **TV-1402 — P0 / M:** Evaluate rules only against newly appended pattern transitions.
- [x] **TV-1403 — P0 / S:** Generate a unique alert fingerprint.
- [x] **TV-1404 — P0 / S:** Create in-app alert events transactionally with pattern transitions.
- [x] **TV-1405 — P0 / S:** Display unread count and newest alerts in the UI.
- [x] **TV-1406 — P0 / S:** Implement acknowledge, acknowledge-all, and mute-pattern actions.
- [x] **TV-1407 — P0 / S:** Include symbol, interval, type, state, score, time, boundary, target, and app link.
- [x] **TV-1408 — P0 / S:** Never send a second alert for score-only changes.
- [x] **TV-1409 — P0 / M:** Add tests for duplicate scans, restarts, state changes, and muted rules.
- [x] **TV-1410 — P1 / M:** Add a notification adapter interface.
- [ ] **TV-1411 — P1 / M:** Implement one external channel only if the user later chooses one; Telegram is explicitly excluded.
- [ ] **TV-1412 — P1 / S:** Store channel secrets only in environment variables.
- [ ] **TV-1413 — P1 / S:** Add a visible “send test notification” action.
- [ ] **TV-1414 — P1 / M:** Retry transient delivery failures with a strict attempt limit.
- [ ] **TV-1415 — P1 / S:** Show permanent failures in diagnostics; never silently discard them.

**Exit criterion:** every confirmed pattern produces zero or one expected alert, and failures are traceable.

### Phase 15 — Scanner and settings UI

- [x] **TV-1501 — P0 / M:** Build the scanner results table with server-side repository filtering.
- [x] **TV-1502 — P0 / S:** Add pattern, direction, state, interval, score, symbol, and time filters.
- [x] **TV-1503 — P0 / S:** Link table rows to the relevant chart and visible date range.
- [x] **TV-1504 — P0 / S:** Add score-reason preview and full detail panel.
- [x] **TV-1505 — P0 / S:** Display last scanner heartbeat, last run, duration, successes, and failures.
- [x] **TV-1506 — P0 / S:** Add CSV export for the currently filtered table.
- [ ] **TV-1507 — P0 / M:** Build detector settings forms from explicit UI code, not dynamic reflection magic.
- [ ] **TV-1508 — P0 / S:** Validate settings before saving and show field-specific errors.
- [ ] **TV-1509 — P0 / S:** Add reset-to-default per detector.
- [ ] **TV-1510 — P0 / S:** Add watchlist management and scan-interval controls.
- [ ] **TV-1511 — P1 / S:** Add data-retention controls with a preview of what will be deleted.
- [x] **TV-1512 — P1 / M:** Add a diagnostics page for package versions, paths, database size, provider health, and recent errors.
- [x] **TV-1513 — P0 / M:** Test callback service boundaries and key page smoke paths.

**Exit criterion:** normal operation and tuning require no database or code edits.

### Phase 16 — Detector validation and backtesting

- [ ] **TV-1601 — P0 / M:** Create a labeling format containing symbol, interval, visible candle range, expected type, pivots, and confirmation.
- [ ] **TV-1602 — P0 / L:** Label an initial balanced set of positive and negative examples for each enabled detector.
- [ ] **TV-1603 — P0 / M:** Freeze source candles for these examples with source and fetch date metadata.
- [ ] **TV-1604 — P0 / M:** Build a time-forward replay that feeds one candle at a time.
- [ ] **TV-1605 — P0 / M:** Report precision, recall, false positives per symbol, and alert latency where labels permit.
- [ ] **TV-1606 — P0 / S:** Report detector coverage separately from profitability.
- [ ] **TV-1607 — P1 / L:** Add an event study for forward returns after confirmation at multiple horizons.
- [ ] **TV-1608 — P1 / M:** Include fees and slippage only in a clearly separate strategy simulation.
- [ ] **TV-1609 — P0 / S:** Split tuning and evaluation periods chronologically.
- [ ] **TV-1610 — P0 / S:** Version detector parameter sets used in each report.
- [ ] **TV-1611 — P0 / S:** Save validation output as human-readable Markdown/CSV.
- [ ] **TV-1612 — P0 / M:** Establish enable-by-default thresholds from validation, not aesthetics.
- [ ] **TV-1613 — P1 / M:** Add regression tests for every corrected false positive.

**Exit criterion:** enabled detectors have documented performance on unseen, time-forward examples.

### Phase 17 — Reliability, performance, and security

- [ ] **TV-1701 — P0 / S:** Measure UI initial load, symbol switch, chart update, and full scan duration.
- [ ] **TV-1702 — P0 / S:** Set performance budgets based on local use.
  - Suggested: cached chart under 1 second; uncached chart under 4 seconds; UI remains responsive during scanning.
- [ ] **TV-1703 — P0 / M:** Add only measured indexes and query optimizations.
- [ ] **TV-1704 — P0 / S:** Limit chart queries to the visible/default window.
- [ ] **TV-1705 — P0 / S:** Limit detector lookback per pattern/interval.
- [ ] **TV-1706 — P1 / M:** Add retention cleanup with dry-run and backup prompts.
- [x] **TV-1707 — P0 / S:** Ensure logs do not contain tokens or full environment dumps.
- [x] **TV-1708 — P0 / S:** Bind the local server to `127.0.0.1` by default.
- [x] **TV-1709 — P0 / XS:** Warn when binding to a non-loopback address without authentication.
- [ ] **TV-1710 — P0 / S:** Escape/sanitize user-visible metadata and constrain imported file paths.
- [ ] **TV-1711 — P0 / S:** Cap batch size, candle lookback, export size, and retry count.
- [x] **TV-1712 — P1 / M:** Add startup database integrity check and documented restore procedure.
- [ ] **TV-1713 — P1 / M:** Run a multi-day local soak test covering scanner restarts and provider failures.
- [x] **TV-1714 — P1 / S:** Add dependency-update and security-audit cadence.

**Exit criterion:** failures degrade visibly, local data can be restored, and no secret is stored in the database or repository.

### Phase 18 — Packaging and personal deployment

- [x] **TV-1801 — P0 / S:** Provide two explicit commands: run UI and run scanner.
- [x] **TV-1802 — P0 / S:** Add a startup check that creates directories, migrates the database, and imports the catalog safely.
- [x] **TV-1803 — P0 / S:** Document first run, normal run, shutdown, update, backup, and restore.
- [x] **TV-1804 — P0 / S:** Display the application version and database schema version.
- [x] **TV-1805 — P1 / M:** Add a simple macOS launch-agent or equivalent user-service example if unattended local scanning is desired.
- [x] **TV-1806 — P1 / M:** Optionally add one Dockerfile and Compose file with UI/scanner services sharing a data volume.
- [x] **TV-1807 — P1 / S:** Add a health command that exits nonzero on stale scanner, corrupt database, or unavailable provider.
- [ ] **TV-1808 — P1 / M:** Produce a release checklist and a versioned first release.

**Exit criterion:** the user can operate and update the application from written instructions without developer improvisation.

### Phase 19 — Post-MVP evolution, only when justified

- [ ] **TV-1901 — P2:** Evaluate a licensed BIST real-time provider using the existing provider contract.
- [ ] **TV-1902 — P2:** Add streaming only if the provider reliably supports it and the product needs sub-candle updates.
- [ ] **TV-1903 — P2:** Add FastAPI when a second client, external integration, or public API is actually required.
- [ ] **TV-1904 — P2:** Move to PostgreSQL when concurrent writers or measured database size make SQLite unsuitable.
- [ ] **TV-1905 — P2:** Add a durable job queue when scanning must scale across machines or survive process loss mid-job.
- [ ] **TV-1906 — P2:** Add authentication before remote/multi-user access.
- [ ] **TV-1907 — P2:** Add portfolio context and position-aware alert priority.
- [ ] **TV-1908 — P2:** Add paper-trading integration before any live brokerage integration.
- [ ] **TV-1909 — P2:** Require a separate safety review, explicit confirmation, and risk controls before live order placement.
- [ ] **TV-1910 — P2:** Investigate machine learning only after a sufficiently large, versioned labeled dataset exists.

---

## 10. Test strategy

### 10.1 Test pyramid

1. **Pure unit tests:** formulas, pivots, pattern geometry, scoring, timestamp boundaries.
2. **Repository tests:** real SQLite temporary database and migrations.
3. **Service tests:** fake provider + real repositories + detectors.
4. **UI smoke tests:** app/layout creation, chart builder, and a small number of critical callbacks.
5. **Live integration tests:** manually invoked, never required for every test run.
6. **Replay validation:** frozen candles delivered one at a time.

### 10.2 Required detector cases

Every detector must test:

- an ideal positive pattern;
- a noisy but acceptable pattern;
- one condition just inside its tolerance;
- the same condition just outside its tolerance;
- insufficient pivot prominence;
- insufficient duration;
- excessive duration;
- forming but not confirmed;
- confirmed at the exact knowable candle;
- invalidated before confirmation;
- expired without confirmation;
- missing volume;
- duplicate timestamps rejected by data quality;
- no mutation of input candles;
- identical result on repeated runs;
- no change to past detections when only unknowable future data is removed.

### 10.3 Provider test symbols

Use a very small representative live set, for example:

- one liquid BIST equity;
- one less-liquid BIST equity;
- one US equity;
- one index or ETF if generic symbols are in scope;
- one deliberately invalid symbol.

Do not make normal CI depend on Yahoo availability.

### 10.4 Definition of a regression fixture

Whenever a real false positive or missed pattern is fixed:

1. save the smallest relevant candle window;
2. remove identifying data only if licensing requires it;
3. record the old incorrect result;
4. add the expected corrected result;
5. pin the relevant detector parameters;
6. keep the fixture permanently unless the detector definition intentionally changes.

---

## 11. Observability and diagnostics

The system should answer these questions without reading source code:

- Is the scanner alive?
- When did each interval last complete?
- How many symbols were requested, succeeded, and failed?
- Which symbols are stale?
- What is the newest candle per interval?
- How long did download, validation, detection, and persistence take?
- Which detector version and parameters created a pattern?
- Why did a pattern receive its score?
- Was an alert deduplicated, muted, acknowledged, delivered, or failed?
- What versions of Python, Dash, Plotly, pandas, NumPy, and yfinance are installed?

Use concise structured fields in ordinary logs, not a separate monitoring stack in version 1.

---

## 12. Suggested default settings for initial testing

These are starting points to validate, not universal truths.

```toml
timezone = "Europe/Istanbul"
database_path = "var/trading_vision.sqlite3"
default_symbol = "THYAO.IS"
default_interval = "1d"
chart_candle_limit = 500
provider_batch_size = 25
provider_max_retries = 3
provider_delay_seconds = 60

[scan]
bist_daily = true
bist_hourly = true
bist_15m = false
watchlist_15m = true
watchlist_5m = false

[patterns]
minimum_alert_score = 70
use_volume_confirmation = true
atr_period = 14
pivot_left_bars = 3
pivot_right_bars = 3
breakout_buffer_atr = 0.10
expiry_bars = 20

[patterns.double_top]
enabled = true
peak_tolerance_percent = 2.0
minimum_depth_atr = 1.0
minimum_bars = 8
maximum_bars = 120

[patterns.head_shoulders]
enabled = false
shoulder_tolerance_percent = 3.0
minimum_head_height_atr = 0.75
maximum_neckline_slope_percent_per_bar = 0.5
```

Enable the more ambiguous detectors only after validation. The settings UI must explain every unit.

---

## 13. MVP cut line

### MVP-A: chart and trustworthy data

Includes Phases 0–7.

Demonstration:

1. start the app;
2. search `THYAO` and load `THYAO.IS`;
3. search a generic Yahoo symbol and load it unchanged;
4. switch daily/hourly/15-minute intervals where data is available;
5. inspect candlesticks, volume, freshness, and provider errors;
6. restart without losing cached candles or watchlist choices.

### MVP-B: first end-to-end detection

Includes Phases 8–10, 13, and in-app portions of 14.

Demonstration:

1. scanner downloads a completed candle;
2. breakout or double-top/bottom detector runs;
3. match is stored once;
4. chart renders its geometry;
5. detail panel explains score and state;
6. confirmation creates one in-app alert;
7. rescanning creates no duplicate.

### Personal release 1.0

Adds head-and-shoulders after validation, scanner/settings UI, reliability work, backups, and operating documentation. Triangles and external notification channels are P1 and may ship shortly after 1.0 if validation is not ready.

---

## 14. Definition of done for release 1.0

Release 1.0 is done only when:

- installation and first run work from the README on a clean supported Python environment;
- the BIST catalog has a recorded official source date;
- arbitrary valid Yahoo symbols can be added without a code change;
- every chart shows source and candle freshness;
- all scans use completed candles by default;
- provider partial failures are visible and do not stop the remaining universe;
- enabled detectors have written definitions and time-forward tests;
- no detector reads future candles;
- pattern overlays, states, score reasons, target, and invalidation are visible;
- duplicate scans do not create duplicate patterns or alerts;
- the scanner resumes after restart and backfills gaps;
- logs and diagnostics answer the health questions in Section 11;
- database backup and restore have been tested;
- the UI binds locally by default;
- secrets are absent from Git, SQLite, and logs;
- lint and tests pass;
- limitations and data-use terms are plainly documented;
- at least one week of ordinary personal use has completed without an unexplained scanner stop.

---

## 15. Decision log with recommended defaults

| Decision | Recommended default | Revisit when |
|---|---|---|
| Local vs hosted | Local single-user | Remote access is explicitly needed |
| UI | Dash + Plotly | Drawing/chart limitations block a required workflow |
| Internal API | Direct service calls | A second client needs the backend |
| Database | SQLite | Measured concurrency/size causes real issues |
| Scanner | Plain Python worker | Durable distributed jobs are required |
| Data provider | yfinance for MVP | Latency/reliability or licensing is insufficient |
| Detection timing | Completed candles | The user deliberately enables provisional signals |
| BIST intraday universe | Watchlist at 15m | Full-universe timing and rate limits are measured safe |
| Prices | Explicit adjusted OHLC | A use case requires separate raw/adjusted views |
| First detectors | Breakouts and double top/bottom | Pipeline and validation are stable |
| Trading | Alerts only | Separate paper/live-trading project is approved |

---

## 16. Recommended implementation order for the first ten working sessions

This is the shortest path to visible value while preserving the architecture.

1. Bootstrap repository, settings, logging, and empty Dash shell.
2. Add SQLite migrations, symbol repository, and initial small BIST catalog fixture.
3. Implement Yahoo single-symbol fetch, normalization, validation, and storage.
4. Build candlestick/volume chart, symbol search, interval selector, and freshness UI.
5. Add batched fetching, full catalog import, watchlist, and provider error reporting.
6. Implement ATR, pivots, synthetic fixtures, and no-future-leakage tests.
7. Implement horizontal breakout detector, persistence, and chart overlay.
8. Implement scanner one-shot mode, scan runs, pattern transitions, and deduplication.
9. Implement continuous worker, heartbeat, in-app alerts, and scanner health UI.
10. Implement double top/bottom, replay tests, settings UI, and manual BIST review.

After session 10, pause feature growth. Use the app, inspect false positives, improve fixtures, and only then proceed to head-and-shoulders and triangles.
