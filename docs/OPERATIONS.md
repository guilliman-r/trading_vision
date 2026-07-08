# Operations guide

This guide is the plain runbook for operating Trading Vision on a local machine.

## First run

1. Create and install the virtual environment from the project root:

   ```bash
   /opt/anaconda3/bin/python3.13 -m venv .venv
   .venv/bin/python -m pip install --upgrade pip
   .venv/bin/python -m pip install -e '.[dev]'
   ```

2. Start the UI:

   ```bash
   .venv/bin/trading-vision-ui
   ```

3. Open <http://127.0.0.1:8050>.
4. Load a small symbol first, such as `THYAO` on `1d`.

On startup, the app creates `var/`, applies SQLite migrations, imports the committed BIST catalog,
and seeds a few fallback symbols. The default database is `var/trading_vision.sqlite3`.

## Normal run

Use two terminals:

- Terminal 1: UI

  ```bash
  .venv/bin/trading-vision-ui
  ```

- Terminal 2: scanner

  ```bash
  .venv/bin/trading-vision-worker
  ```

For a safe scanner smoke test, run:

```bash
.venv/bin/trading-vision-worker --once --force --dry-run --max-symbols 5 --intervals 1d
```

To check whether the local database, scanner heartbeat, and provider are healthy:

```bash
.venv/bin/trading-vision-health
```

The command returns exit code `0` only when all checks pass. It exits nonzero if SQLite appears
corrupt, the scanner heartbeat is missing/stale/stopped, or the provider smoke request fails.
For a no-network local check, run:

```bash
.venv/bin/trading-vision-health --skip-provider
```

If you want the scanner to run unattended after macOS login, follow the optional
[LaunchAgent example](LAUNCH_AGENT.md). Do this only after manual scanner runs and health checks
already work.

If you prefer containers instead of a local virtual environment, use the optional
[Docker and Compose guide](DOCKER.md). It keeps the UI on localhost and shares `./var` between the
UI and scanner services.

For monthly dependency review and pre-release security checks, follow the
[maintenance cadence](MAINTENANCE.md).

The UI is local-only by default at `127.0.0.1:8050`. Keep it that way unless you deliberately intend
to expose an unauthenticated local app on a trusted network.

## Shutdown

Stop the scanner with `Ctrl-C` first, then stop the UI with `Ctrl-C`.

The scanner writes a final `stopped` heartbeat when it exits cleanly. If a later scanner start says
another scanner owns `var/scanner.lock`, check whether an old process is still running before
removing the lock file.

## Update

1. Stop the scanner and UI.
2. Create a backup:

   ```bash
   .venv/bin/trading-vision-db backup --output var/trading_vision.before-update.sqlite3
   ```

3. Pull the latest code and reinstall the editable package:

   ```bash
   git pull
   .venv/bin/python -m pip install -e '.[dev]'
   ```

4. Run the local quality gate if you changed code locally:

   ```bash
   .venv/bin/python -m ruff format --check .
   .venv/bin/python -m ruff check .
   .venv/bin/python -m pytest
   ```

5. Start the UI. Migrations run automatically at startup.
6. Start the scanner after the UI opens normally.

## Backup

Create a SQLite-safe backup copy:

```bash
.venv/bin/trading-vision-db backup --output var/trading_vision.backup.sqlite3
```

Check the current database path and table counts:

```bash
.venv/bin/trading-vision-db stats
```

If you use `config.toml` or `TV_DATABASE_PATH`, back up the configured database path, not only the
default `var/trading_vision.sqlite3`.

## Restore

1. Stop the scanner and UI.
2. Keep a copy of the current database before replacing it:

   ```bash
   cp var/trading_vision.sqlite3 var/trading_vision.failed-restore-source.sqlite3
   ```

3. Copy the chosen backup over the active database:

   ```bash
   cp var/trading_vision.backup.sqlite3 var/trading_vision.sqlite3
   ```

4. Check the restored database before starting the scanner:

   ```bash
   .venv/bin/trading-vision-health --skip-provider
   .venv/bin/trading-vision-db stats
   ```

5. Start the UI:

   ```bash
   .venv/bin/trading-vision-ui
   ```

6. Confirm the chart opens and the scanner diagnostics load.
7. Start the scanner only after the restored UI looks healthy.

If the restored file came from an older version, startup migrations will apply forward-only schema
changes automatically. UI and scanner startup also run SQLite `quick_check`; if that fails, restore
from a different backup before continuing.
