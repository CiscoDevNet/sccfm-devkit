# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from cisco_sccfm_cli.models import Config
from cisco_sccfm_cli.services import ConfigService


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


def test_should_harden_config_file_permissions(tmp_path: Path) -> None:
    config_path = tmp_path / "profiles" / "config.json"
    service = ConfigService(path=config_path)

    service.save(Config(profile="default", region="us", api_token="secret-token"))

    assert config_path.stat().st_mode & 0o777 == 0o600
    assert config_path.parent.stat().st_mode & 0o777 == 0o700


def test_should_harden_existing_config_file_on_open(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"profiles": {}}\n')
    config_path.chmod(0o644)

    ConfigService(path=config_path)

    assert config_path.stat().st_mode & 0o777 == 0o600


def test_should_replace_config_atomically_without_leaving_temporary_files(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    service = ConfigService(path=config_path)
    service.save(Config(profile="default", region="us", api_token="first-token"))

    service.save(Config(profile="default", region="eu", api_token="second-token"))

    assert json.loads(config_path.read_text())["profiles"]["default"] == {
        "region": "eu",
        "api_token": "second-token",
    }
    assert list(tmp_path.glob(".config.json.*.tmp")) == []


def test_should_remove_profile(tmp_path: Path) -> None:
    service = ConfigService(path=tmp_path / "config.json")
    service.save(Config(profile="default", region="us", api_token="default-token"))
    service.save(Config(profile="lab", region="eu", api_token="lab-token"))

    assert service.remove("lab") is True
    assert service.load("lab") is None
    assert [profile.profile for profile in service.list_profiles()] == ["default"]
    assert service.remove("missing") is False


def test_should_honor_canonical_config_path_override(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    config_path = tmp_path / "custom.json"
    monkeypatch.setenv("SCCFM_CONFIG", str(config_path))

    ConfigService().save(Config(profile="lab", region="eu", api_token="token"))

    assert ConfigService().load("lab") == Config(profile="lab", region="eu", api_token="token")
    assert config_path.is_file()
