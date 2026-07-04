from pathlib import Path

import pytest

from trading_vision.config import Settings, load_settings


def test_default_settings_are_valid() -> None:
    assert Settings().validate().default_symbol == "THYAO.IS"


def test_loads_relative_database_path_from_toml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[storage]\ndatabase_path = "var/example.sqlite3"\n')
    settings = load_settings(config_path)
    assert settings.database_path.name == "example.sqlite3"
    assert settings.database_path.is_absolute()


def test_rejects_unknown_interval() -> None:
    with pytest.raises(ValueError, match="Unsupported interval"):
        Settings(default_interval="2h").validate()


def test_loads_scanner_settings_and_resolves_lock_path(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[scanner]\nintervals = ["1d", "1h"]\nbatch_size = 10\n'
        'lookback_bars = 400\nprovider_delay_seconds = 90\nlock_path = "var/test.lock"\n'
    )
    settings = load_settings(config_path)
    assert settings.scan_intervals == ("1d", "1h")
    assert settings.scanner_batch_size == 10
    assert settings.scanner_lookback_bars == 400
    assert settings.provider_delay_seconds == 90
    assert settings.scanner_lock_path.is_absolute()
