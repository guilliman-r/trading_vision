## Summary

- TBD

## Checklist

- [ ] The change keeps Trading Vision local-first and single-user.
- [ ] The change does not add broker credentials, order placement, or order-routing behavior.
- [ ] User-facing behavior is documented in `README.md` or `docs/` when relevant.
- [ ] Database changes are additive migrations and include fresh-SQLite tests.
- [ ] Pattern, scanner, or alert behavior changes include deterministic tests.
- [ ] UI changes are checked for readability and avoid crowding the chart.
- [ ] Logs and diagnostics do not print secrets, tokens, or full environment dumps.
- [ ] No external notification channel is added unless the user explicitly chooses one.
- [ ] `ruff format --check .`, `ruff check .`, and `pytest` pass locally.

## Manual verification

- TBD
