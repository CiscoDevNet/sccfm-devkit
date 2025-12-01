from __future__ import annotations

from pathlib import Path

from sccfm_cli.models import Config
from sccfm_cli.services import ConfigService


def test_should_save_and_load_config(tmp_path: Path) -> None:
    """ConfigService should persist and retrieve configuration."""
    config_path = tmp_path / "config.json"
    service = ConfigService(path=config_path)

    expected = Config(profile="default", region="us", api_token="secret-token")
    service.save(expected)

    loaded = service.load("default")
    assert loaded == expected


def test_should_list_all_profiles(tmp_path: Path) -> None:
    """ConfigService should list all saved profiles."""
    config_path = tmp_path / "config.json"
    service = ConfigService(path=config_path)

    expected = Config(profile="default", region="us", api_token="secret-token")
    service.save(expected)

    profiles = service.list_profiles()
    assert profiles == [expected]
