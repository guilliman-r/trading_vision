from pathlib import Path

import pytest

from trading_vision.config import (
    Settings,
    host_binding_warning,
    load_settings,
    main,
    public_settings,
)


def test_default_settings_are_valid() -> None:
    assert Settings().validate().default_symbol == "THYAO.IS"


def test_loads_relative_database_path_from_toml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[storage]\ndatabase_path = "var/example.sqlite3"\n')
    settings = load_settings(config_path)
    assert settings.database_path.name == "example.sqlite3"
    assert settings.database_path.is_absolute()


def test_loads_and_validates_logging_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[logging]\npath = "var/example.log"\nlevel = "debug"\n')

    settings = load_settings(config_path)

    assert settings.log_path.name == "example.log"
    assert settings.log_path.is_absolute()
    assert settings.log_level == "DEBUG"
    with pytest.raises(ValueError, match="log_level"):
        Settings(log_level="verbose").validate()


def test_loads_and_validates_timezone(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[app]\ntimezone = "UTC"\n')

    assert load_settings(config_path).timezone == "UTC"
    with pytest.raises(ValueError, match="Unsupported timezone"):
        Settings(timezone="Mars/Olympus").validate()


def test_rejects_unknown_interval() -> None:
    with pytest.raises(ValueError, match="Unsupported interval"):
        Settings(default_interval="2h").validate()


def test_only_daily_and_hourly_intervals_are_user_supported() -> None:
    assert Settings(default_interval="1h").validate().default_interval == "1h"
    with pytest.raises(ValueError, match="Unsupported interval"):
        Settings(default_interval="15m").validate()
    with pytest.raises(ValueError, match="Unsupported scan intervals: 15m"):
        Settings(scan_intervals=("15m",)).validate()


def test_loads_scanner_settings_and_resolves_lock_path(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[scanner]\nintervals = ["1d", "1h"]\nbatch_size = 10\n'
        "export_limit = 750\nlookback_bars = 400\n"
        'provider_delay_seconds = 90\nlock_path = "var/test.lock"\n'
    )
    settings = load_settings(config_path)
    assert settings.scan_intervals == ("1d", "1h")
    assert settings.scanner_batch_size == 10
    assert settings.scanner_export_limit == 750
    assert settings.scanner_lookback_bars == 400
    assert settings.provider_delay_seconds == 90
    assert settings.scanner_lock_path.is_absolute()


def test_scanner_export_limit_is_capped() -> None:
    with pytest.raises(ValueError, match="scanner_export_limit"):
        Settings(scanner_export_limit=2_001).validate()


def test_loads_and_validates_alert_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[alerts]\nminimum_score = 80\nenabled_pattern_types = ["double_top"]\n')
    settings = load_settings(config_path)
    assert settings.minimum_alert_score == 80
    assert settings.alert_pattern_types == ("double_top",)
    with pytest.raises(ValueError, match="minimum_alert_score"):
        Settings(minimum_alert_score=101).validate()


def test_loads_and_validates_provider_cooldown(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[provider]\ncooldown_seconds = 45\n")

    assert load_settings(config_path).provider_cooldown_seconds == 45
    with pytest.raises(ValueError, match="provider_cooldown_seconds"):
        Settings(provider_cooldown_seconds=301).validate()


def test_loopback_host_does_not_warn() -> None:
    assert host_binding_warning(Settings(host="127.0.0.1")) is None
    assert host_binding_warning(Settings(host="localhost")) is None
    assert host_binding_warning(Settings(host="::1")) is None


def test_non_loopback_host_warns_about_missing_authentication() -> None:
    warning = host_binding_warning(Settings(host="0.0.0.0"))

    assert warning is not None
    assert "no authentication" in warning
    assert "127.0.0.1" in warning


def test_public_settings_are_an_explicit_non_secret_allowlist() -> None:
    settings = Settings(host="127.0.0.1", scan_intervals=("1d", "1h"))

    values = public_settings(settings)

    assert values["host"] == "127.0.0.1"
    assert values["scan_intervals"] == "1d, 1h"
    assert "environment" not in values
    assert "token" not in values


def test_config_command_prints_effective_non_secret_settings(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[app]\nhost = "localhost"\nport = 9000\n')
    monkeypatch.setenv("TV_FAKE_SECRET_TOKEN", "do-not-print")

    main(["--config", str(config_path)])

    output = capsys.readouterr().out
    assert "host=localhost" in output
    assert "port=9000" in output
    assert "TV_FAKE_SECRET_TOKEN" not in output
    assert "do-not-print" not in output
