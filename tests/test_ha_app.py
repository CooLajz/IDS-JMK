"""Check Supervisor option handling without importing or starting the API."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "home-assistant/ids_jmk"
spec = importlib.util.spec_from_file_location("ha_run", APP / "run.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_supervisor_defaults_match_api(monkeypatch):
    config = json.loads((APP / "config.json").read_text())
    environment = launcher.options_environment(config["options"])
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    # A fresh module is necessary: Settings reads the environment at import time.
    config_spec = importlib.util.spec_from_file_location("api_settings", ROOT / "api/config.py")
    module = importlib.util.module_from_spec(config_spec)
    config_spec.loader.exec_module(module)
    settings = module.Settings()
    assert settings.realtime_enabled is False
    assert settings.gtfs_interval == 86400
    assert settings.realtime_interval == 60
    assert settings.realtime_max_age == 180
    assert settings.realtime_idle_timeout == 300
    assert launcher.options_environment({}) == environment


def test_custom_options():
    assert launcher.options_environment({
        "realtime_enabled": True, "gtfs_interval_seconds": 3600,
        "realtime_interval_seconds": 15, "realtime_max_age_seconds": 30,
    }) == {
        "REALTIME_ENABLED": "true", "GTFS_INTERVAL_SECONDS": "3600",
        "REALTIME_INTERVAL_SECONDS": "15", "REALTIME_MAX_AGE_SECONDS": "30",
        "REALTIME_IDLE_TIMEOUT_SECONDS": "300",
    }


@pytest.mark.parametrize("options", [
    {"realtime_idle_timeout_seconds": -1}, {"realtime_idle_timeout_seconds": True},
    [], None, {"realtime_enabled": "false"}, {"realtime_enabled": 1},
    {"gtfs_interval_seconds": 3599}, {"realtime_interval_seconds": 14},
    {"realtime_max_age_seconds": 29}, {"gtfs_interval_seconds": True},
    {"realtime_interval_seconds": "60"}, {"realtime_max_age_seconds": 60.5},
])
def test_invalid_options_fail_before_start(options):
    with pytest.raises(ValueError):
        launcher.options_environment(options)
