# macOS LaunchAgent example

Use this only if you want the scanner to run unattended after you log in to macOS. It is optional:
you can keep using `.venv/bin/trading-vision-worker` in a terminal.

The LaunchAgent should run the scanner, not the UI. Keep the UI as a normal local app that you open
when you want to review charts.

## Example plist

Save this as `~/Library/LaunchAgents/com.tradingvision.scanner.plist` and replace
`/Users/guilliman/Developer/trading_vision` if your project lives somewhere else.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.tradingvision.scanner</string>

  <key>WorkingDirectory</key>
  <string>/Users/guilliman/Developer/trading_vision</string>

  <key>ProgramArguments</key>
  <array>
    <string>/Users/guilliman/Developer/trading_vision/.venv/bin/trading-vision-worker</string>
  </array>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>/Users/guilliman/Developer/trading_vision/var/launch-agent.out.log</string>

  <key>StandardErrorPath</key>
  <string>/Users/guilliman/Developer/trading_vision/var/launch-agent.err.log</string>
</dict>
</plist>
```

## Load, check, and unload

From the project root:

```bash
mkdir -p var ~/Library/LaunchAgents
cp docs/examples/com.tradingvision.scanner.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.tradingvision.scanner.plist
launchctl print "gui/$(id -u)/com.tradingvision.scanner"
.venv/bin/trading-vision-health --skip-provider
```

To stop the unattended scanner:

```bash
launchctl bootout "gui/$(id -u)/com.tradingvision.scanner"
```

## Safety notes

- Reinstall the editable package after pulling updates: `.venv/bin/python -m pip install -e '.[dev]'`.
- Run `.venv/bin/trading-vision-health --skip-provider` after loading the agent.
- If the health command reports a stopped or stale scanner, inspect `var/launch-agent.err.log` first.
- Do not create multiple LaunchAgents for the same database; the scanner lock is designed to reject
  a second worker, but duplicated services make diagnosis noisy.
