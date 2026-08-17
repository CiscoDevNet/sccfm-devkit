# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from _pytest.monkeypatch import MonkeyPatch

from cisco_sccfm_core.models.profile import Profile
from cisco_sccfm_core.services import profile_service
from cisco_sccfm_core.services.profile_service import ProfileService


def test_should_save_and_load_profile(tmp_path: Path) -> None:
    """ProfileService should persist and retrieve a profile."""
    service = ProfileService(path=tmp_path / "config.json")

    expected = Profile(profile="default", region="us", api_token="secret-token")
    service.save(expected)

    assert service.load("default") == expected


def test_should_return_none_for_unknown_profile(tmp_path: Path) -> None:
    service = ProfileService(path=tmp_path / "config.json")

    assert service.load("missing") is None


def test_should_list_all_profiles_sorted_by_name(tmp_path: Path) -> None:
    service = ProfileService(path=tmp_path / "config.json")
    service.save(Profile(profile="lab", region="eu", api_token="lab-token"))
    service.save(Profile(profile="default", region="us", api_token="default-token"))

    assert [profile.profile for profile in service.list_profiles()] == ["default", "lab"]


def test_should_remove_profile(tmp_path: Path) -> None:
    service = ProfileService(path=tmp_path / "config.json")
    service.save(Profile(profile="default", region="us", api_token="default-token"))
    service.save(Profile(profile="lab", region="eu", api_token="lab-token"))

    assert service.remove("lab") is True
    assert service.load("lab") is None
    assert [profile.profile for profile in service.list_profiles()] == ["default"]
    assert service.remove("missing") is False


def test_should_harden_config_file_permissions(tmp_path: Path) -> None:
    config_path = tmp_path / "profiles" / "config.json"
    service = ProfileService(path=config_path)

    service.save(Profile(profile="default", region="us", api_token="secret-token"))

    assert config_path.stat().st_mode & 0o777 == 0o600
    assert config_path.parent.stat().st_mode & 0o777 == 0o700


def test_should_harden_existing_config_file_on_open(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"profiles": {}}\n')
    config_path.chmod(0o644)

    ProfileService(path=config_path)

    assert config_path.stat().st_mode & 0o777 == 0o600


def test_should_replace_config_atomically_without_leaving_temporary_files(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    service = ProfileService(path=config_path)
    service.save(Profile(profile="default", region="us", api_token="first-token"))

    service.save(Profile(profile="default", region="eu", api_token="second-token"))

    assert json.loads(config_path.read_text())["profiles"]["default"] == {
        "region": "eu",
        "api_token": "second-token",
    }
    assert list(tmp_path.glob(".config.json.*.tmp")) == []


def test_should_honor_canonical_config_path_override(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    config_path = tmp_path / "custom.json"
    monkeypatch.setenv("SCCFM_CONFIG", str(config_path))

    ProfileService().save(Profile(profile="lab", region="eu", api_token="token"))

    assert ProfileService().load("lab") == Profile(profile="lab", region="eu", api_token="token")
    assert config_path.is_file()


def test_should_save_profile_without_posix_mode_apis(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(profile_service, "_SUPPORTS_POSIX_MODES", False)
    fchmod = MagicMock()
    monkeypatch.setattr(profile_service.os, "fchmod", fchmod, raising=False)

    ProfileService(path=config_path).save(
        Profile(profile="default", region="us", api_token="secret-token")
    )

    fchmod.assert_not_called()
    assert ProfileService(path=config_path).load("default") == Profile(
        profile="default", region="us", api_token="secret-token"
    )
