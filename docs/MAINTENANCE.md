# Maintenance cadence

Trading Vision should stay boring to operate. Dependency updates and security checks are manual,
reviewed, and tested before they are pushed.

## Monthly dependency review

Once a month:

```bash
.venv/bin/python -m pip list --outdated
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m ruff format --check .
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
```

If you choose to update dependencies, update only a small group at a time, run the full gates, and
record notable behavior changes in `CHANGELOG.md`.

## Security audit before a release

Before tagging or publishing a release, run an audit with your preferred local tool. For example,
if `pip-audit` is available on your machine:

```bash
pip-audit
```

If an audit reports an issue:

1. Check whether the affected package is installed directly or as a transitive dependency.
2. Upgrade the smallest safe dependency set.
3. Run format, lint, and tests.
4. Record the fix or accepted risk in the release checklist.

Do not add secrets, tokens, full environment dumps, or private local paths to audit logs committed
to the repository.

## After updating

Use this short verification set:

```bash
.venv/bin/trading-vision-db stats
.venv/bin/trading-vision-health --skip-provider
.venv/bin/python scripts/check_data.py
```

Then manually open the UI, load `THYAO` on `1d`, and confirm the chart and scanner workspace render.
