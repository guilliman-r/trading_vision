"""Small, explicit application configuration."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, replace
from ipaddress import ip_address
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_INTERVALS = ("1d", "1h", "15m", "5m")
SUPPORTED_SCAN_INTERVALS = ("1d", "1h", "15m")
SUPPORTED_PATTERN_TYPES = (
    "resistance_breakout",
    "support_breakdown",
    "double_top",
    "double_bottom",
    "head_shoulders",
    "inverse_head_shoulders",
    "ascending_triangle",
    "descending_triangle",
    "symmetrical_triangle",
)
LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings shared by the UI and future scanner process."""

    database_path: Path = PROJECT_ROOT / "var" / "trading_vision.sqlite3"
    log_path: Path = PROJECT_ROOT / "var" / "trading_vision.log"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8050
    debug: bool = False
    timezone: str = "Europe/Istanbul"
    default_symbol: str = "THYAO.IS"
    default_interval: str = "1d"
    chart_candle_limit: int = 500
    scan_intervals: tuple[str, ...] = ("1d",)
    scanner_batch_size: int = 25
    scanner_lookback_bars: int = 500
    provider_delay_seconds: int = 60
    provider_cooldown_seconds: int = 30
    scanner_lock_path: Path = PROJECT_ROOT / "var" / "scanner.lock"
    minimum_alert_score: float = 70.0
    alert_pattern_types: tuple[str, ...] = (
        "resistance_breakout",
        "support_breakdown",
    )

    def validate(self) -> Settings:
        if self.default_interval not in SUPPORTED_INTERVALS:
            allowed = ", ".join(SUPPORTED_INTERVALS)
            raise ValueError(f"Unsupported interval {self.default_interval!r}; use {allowed}")
        if not 1 <= self.port <= 65_535:
            raise ValueError("Port must be between 1 and 65535")
        if self.log_level.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("log_level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"Unsupported timezone: {self.timezone}") from error
        if not 50 <= self.chart_candle_limit <= 5_000:
            raise ValueError("chart_candle_limit must be between 50 and 5000")
        invalid_scan_intervals = set(self.scan_intervals).difference(SUPPORTED_SCAN_INTERVALS)
        if invalid_scan_intervals:
            invalid = ", ".join(sorted(invalid_scan_intervals))
            allowed = ", ".join(SUPPORTED_SCAN_INTERVALS)
            raise ValueError(f"Unsupported scan intervals: {invalid}; use {allowed}")
        if not self.scan_intervals:
            raise ValueError("At least one scan interval is required")
        if not 1 <= self.scanner_batch_size <= 100:
            raise ValueError("scanner_batch_size must be between 1 and 100")
        if not 350 <= self.scanner_lookback_bars <= 5_000:
            raise ValueError("scanner_lookback_bars must be between 350 and 5000")
        if not 0 <= self.provider_delay_seconds <= 3_600:
            raise ValueError("provider_delay_seconds must be between 0 and 3600")
        if not 0 <= self.provider_cooldown_seconds <= 300:
            raise ValueError("provider_cooldown_seconds must be between 0 and 300")
        if not 0 <= self.minimum_alert_score <= 100:
            raise ValueError("minimum_alert_score must be between 0 and 100")
        invalid_pattern_types = set(self.alert_pattern_types).difference(SUPPORTED_PATTERN_TYPES)
        if invalid_pattern_types:
            invalid = ", ".join(sorted(invalid_pattern_types))
            raise ValueError(f"Unsupported alert pattern types: {invalid}")
        return self


def load_settings(config_path: Path | None = None) -> Settings:
    """Load defaults, optional TOML, then the few supported environment overrides."""

    settings = Settings()
    path = config_path or PROJECT_ROOT / "config.toml"
    if path.exists():
        with path.open("rb") as file:
            document = tomllib.load(file)
        app = document.get("app", {})
        storage = document.get("storage", {})
        scanner = document.get("scanner", {})
        provider = document.get("provider", {})
        alerts = document.get("alerts", {})
        logging_settings = document.get("logging", {})
        raw_database_path = storage.get("database_path", str(settings.database_path))
        database_path = Path(raw_database_path)
        if not database_path.is_absolute():
            database_path = PROJECT_ROOT / database_path
        raw_log_path = logging_settings.get("path", str(settings.log_path))
        log_path = Path(raw_log_path)
        if not log_path.is_absolute():
            log_path = PROJECT_ROOT / log_path
        raw_lock_path = scanner.get("lock_path", str(settings.scanner_lock_path))
        scanner_lock_path = Path(raw_lock_path)
        if not scanner_lock_path.is_absolute():
            scanner_lock_path = PROJECT_ROOT / scanner_lock_path
        settings = replace(
            settings,
            database_path=database_path,
            log_path=log_path,
            log_level=str(logging_settings.get("level", settings.log_level)).upper(),
            host=str(app.get("host", settings.host)),
            port=int(app.get("port", settings.port)),
            debug=bool(app.get("debug", settings.debug)),
            timezone=str(app.get("timezone", settings.timezone)),
            default_symbol=str(app.get("default_symbol", settings.default_symbol)).upper(),
            default_interval=str(app.get("default_interval", settings.default_interval)),
            chart_candle_limit=int(app.get("chart_candle_limit", settings.chart_candle_limit)),
            scan_intervals=tuple(scanner.get("intervals", settings.scan_intervals)),
            scanner_batch_size=int(scanner.get("batch_size", settings.scanner_batch_size)),
            scanner_lookback_bars=int(scanner.get("lookback_bars", settings.scanner_lookback_bars)),
            provider_delay_seconds=int(
                scanner.get("provider_delay_seconds", settings.provider_delay_seconds)
            ),
            provider_cooldown_seconds=int(
                provider.get("cooldown_seconds", settings.provider_cooldown_seconds)
            ),
            scanner_lock_path=scanner_lock_path,
            minimum_alert_score=float(alerts.get("minimum_score", settings.minimum_alert_score)),
            alert_pattern_types=tuple(
                alerts.get("enabled_pattern_types", settings.alert_pattern_types)
            ),
        )

    environment_values: dict[str, object] = {}
    if os.getenv("TV_DATABASE_PATH"):
        environment_values["database_path"] = Path(os.environ["TV_DATABASE_PATH"]).expanduser()
    if os.getenv("TV_HOST"):
        environment_values["host"] = os.environ["TV_HOST"]
    if os.getenv("TV_PORT"):
        environment_values["port"] = int(os.environ["TV_PORT"])
    return replace(settings, **environment_values).validate()


def host_binding_warning(settings: Settings) -> str | None:
    """Warn when the unauthenticated local app is bound beyond loopback."""

    host = settings.host.strip().lower()
    if _is_loopback_host(host):
        return None
    return (
        f"Warning: Trading Vision is configured to bind to {settings.host!r}. "
        "Version 1 has no authentication, so prefer 127.0.0.1 unless you are deliberately "
        "exposing the local app on a trusted network."
    )


def _is_loopback_host(host: str) -> bool:
    if host in LOOPBACK_HOSTNAMES:
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False
