# In-app alert guide

Alerts are immutable snapshots of meaningful pattern state changes. They are decision-support
signals, not trading instructions or estimates of profitability.

## Default rule

The application maintains one explicit system rule:

- required state: `confirmed`;
- minimum score: 70;
- enabled types: `resistance_breakout` and `support_breakdown`;
- active by default.

Configure it in `config.toml`:

```toml
[alerts]
minimum_score = 70
enabled_pattern_types = ["resistance_breakout", "support_breakdown"]
```

The rule row is synchronized from these non-secret settings while its active/disabled state remains
under database control. Head-and-shoulders and triangle alerts stay off until frozen real positive
and negative fixtures are reviewed. Adding a type is deliberate and visible.

## Creation contract

The alert evaluator runs only when a new `pattern_transitions` row is appended. It never runs for a
score-only update or an identical rescan. A match must satisfy the active rule and not be muted.

Directly discovered confirmed patterns alert only when confirmation is within one completed candle
of the newest stored candle. This prevents the first scan of a long history from flooding the
notification center. A previously stored `forming` pattern that becomes `confirmed` can alert after
offline catch-up even when its confirmation is older.

Pattern transition and alert event writes share one SQLite transaction. If event creation fails,
the transition is rolled back with it.

## Deduplication

The fingerprint is a SHA-256-derived value of:

```text
rule ID + stable pattern ID + new state
```

`alert_events.fingerprint` is unique in SQLite. Repeated scans, score changes, process restarts, and
retrying the same transition therefore cannot create a second event.

## Event contents

Every event stores the provider symbol, interval, pattern type, direction, state, score, event time,
boundary, optional target, stable pattern ID, transition, rule, and local application link. The
event remains an audit snapshot even if the current pattern later invalidates.

## Notification center

The top bar shows unread count. The right panel refreshes every 15 seconds and lists the 20 newest
events. Available actions are:

- acknowledge one event;
- acknowledge all unread events;
- mute the pattern and acknowledge all existing events for that pattern;
- open its stored chart context link.

Actions are idempotent and each callback uses a short-lived SQLite connection. Muting does not
delete history.

## External delivery

`NotificationAdapter` is the replaceable contract for a future Telegram, email, or desktop sender.
No external channel is enabled, no delivery credentials are requested, and no network message is
sent in v0.7. Delivery persistence, retries, test-message controls, and visible permanent failures
remain open roadmap items.
