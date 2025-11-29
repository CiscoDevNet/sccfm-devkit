from __future__ import annotations

from pathlib import Path

from sccfm_cli.models import Config
from sccfm_cli.services import ConfigService


def test_config_service_round_trip(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    service = ConfigService(path=config_path)

    expected = Config(profile="default", region="us", api_token="secret-token")
    service.save(expected)

    loaded = service.load("default")
    assert loaded == expected

    profiles = service.list_profiles()
    assert profiles == [expected]
