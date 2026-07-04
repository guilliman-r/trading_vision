"""Small, explicit application configuration."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_INTERVALS = ("1d", "1h", "15m", "5m")


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings shared by the UI and future scanner process."""

    database_path: Path = PROJECT_ROOT / "var" / "trading_vision.sqlite3"
    host: str = "127.0.0.1"
    port: int = 8050
    debug: bool = False
    default_symbol: str = "THYAO.IS"
    default_interval: str = "1d"
    chart_candle_limit: int = 500

    def validate(self) -> Settings:
        if self.default_interval not in SUPPORTED_INTERVALS:
            allowed = ", ".join(SUPPORTED_INTERVALS)
            raise ValueError(f"Unsupported interval {self.default_interval!r}; use {allowed}")
        if not 1 <= self.port <= 65_535:
            raise ValueError("Port must be between 1 and 65535")
        if not 50 <= self.chart_candle_limit <= 5_000:
            raise ValueError("chart_candle_limit must be between 50 and 5000")
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
        raw_database_path = storage.get("database_path", str(settings.database_path))
        database_path = Path(raw_database_path)
        if not database_path.is_absolute():
            database_path = PROJECT_ROOT / database_path
        settings = replace(
            settings,
            database_path=database_path,
            host=str(app.get("host", settings.host)),
            port=int(app.get("port", settings.port)),
            debug=bool(app.get("debug", settings.debug)),
            default_symbol=str(app.get("default_symbol", settings.default_symbol)).upper(),
            default_interval=str(app.get("default_interval", settings.default_interval)),
            chart_candle_limit=int(app.get("chart_candle_limit", settings.chart_candle_limit)),
        )

    environment_values: dict[str, object] = {}
    if os.getenv("TV_DATABASE_PATH"):
        environment_values["database_path"] = Path(os.environ["TV_DATABASE_PATH"]).expanduser()
    if os.getenv("TV_HOST"):
        environment_values["host"] = os.environ["TV_HOST"]
    if os.getenv("TV_PORT"):
        environment_values["port"] = int(os.environ["TV_PORT"])
    return replace(settings, **environment_values).validate()
