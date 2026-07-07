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

4. Start the UI:

   ```bash
   .venv/bin/trading-vision-ui
   ```

5. Confirm the chart opens and the scanner diagnostics load.
6. Start the scanner only after the restored UI looks healthy.

If the restored file came from an older version, startup migrations will apply forward-only schema
changes automatically.
