# Docker and Compose example

This is optional. The normal local workflow remains the easiest path:

```bash
.venv/bin/trading-vision-ui
.venv/bin/trading-vision-worker
```

Use Docker only if you want the UI and scanner to run as repeatable services with a shared local
`var/` directory.

## Start

From the project root:

```bash
docker compose up --build
```

Open <http://127.0.0.1:8050>.

The Compose file starts:

- `ui`: runs `trading-vision-ui`, exposed only on `127.0.0.1:8050`.
- `scanner`: runs `trading-vision-worker`.

Both services mount `./var` to `/app/var`, so they share the same SQLite database, scanner lock,
logs, and generated files.

## Stop

```bash
docker compose down
```

The local data remains in `./var`.

## Health check

After both services start, run:

```bash
docker compose exec ui trading-vision-health --skip-provider
```

Use the non-Docker `.venv/bin/trading-vision-health` command if you are running the app directly on
macOS.

## Notes

- The Compose example intentionally does not expose the unauthenticated app beyond localhost.
- Rebuild after dependency or code changes: `docker compose build`.
- Keep only one scanner service pointed at a database. The scanner lock prevents duplicate work, but
  one worker is the clean operating model.
