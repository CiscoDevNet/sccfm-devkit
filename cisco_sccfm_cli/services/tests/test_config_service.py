# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any, TextIO

import pytest

from cisco_sccfm_cli.models import Config
from cisco_sccfm_cli.services import ConfigService
from cisco_sccfm_cli.services import config_service as config_service_module

POSIX_ONLY = pytest.mark.skipif(
    os.name != "posix",
    reason="POSIX permission bits are not portable to this platform",
)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _write_config(path: Path, profile: str = "default") -> Config:
    expected = Config(profile=profile, region="us", api_token="example-token")
    path.write_text(
        json.dumps(
            {
                "profiles": {
                    profile: {
                        "region": expected.region,
                        "api_token": expected.api_token,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return expected


def _use_default_path(monkeypatch: pytest.MonkeyPatch, config_path: Path) -> None:
    monkeypatch.setattr(config_service_module, "_CONFIG_DIR", config_path.parent)
    monkeypatch.setattr(config_service_module, "_CONFIG_FILE", config_path)


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


@POSIX_ONLY
def test_new_custom_storage_is_private_before_payload_is_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """New custom storage should be private as soon as its payload is written."""
    config_path = tmp_path / "custom" / "config.json"
    original_dump = json.dump
    modes_during_write: list[int] = []

    def observe_mode(payload: Any, handle: TextIO, *, indent: int) -> None:
        modes_during_write.append(_mode(config_path))
        original_dump(payload, handle, indent=indent)

    monkeypatch.setattr(config_service_module.json, "dump", observe_mode)

    ConfigService(path=config_path).save(
        Config(profile="default", region="us", api_token="example-token")
    )

    assert modes_during_write == [0o600]
    assert _mode(config_path.parent) == 0o700
    assert _mode(config_path) == 0o600


@POSIX_ONLY
def test_new_default_storage_is_private(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default config directory and file should be private when created."""
    config_path = tmp_path / ".sccfm-cli" / "config.json"
    _use_default_path(monkeypatch, config_path)

    ConfigService().save(Config(profile="default", region="us", api_token="example-token"))

    assert _mode(config_path.parent) == 0o700
    assert _mode(config_path) == 0o600


@POSIX_ONLY
def test_load_hardens_existing_custom_file_without_changing_parent(tmp_path: Path) -> None:
    """Loading should harden the file but respect an existing custom directory."""
    custom_parent = tmp_path / "shared-config"
    custom_parent.mkdir()
    custom_parent.chmod(0o750)
    config_path = custom_parent / "config.json"
    expected = _write_config(config_path)
    config_path.chmod(0o644)

    loaded = ConfigService(path=config_path).load(expected.profile)

    assert loaded == expected
    assert _mode(config_path) == 0o600
    assert _mode(custom_parent) == 0o750


@POSIX_ONLY
def test_save_hardens_existing_file_without_replacing_it(tmp_path: Path) -> None:
    """Saving should remain a direct write while hardening existing storage."""
    custom_parent = tmp_path / "shared-config"
    custom_parent.mkdir()
    custom_parent.chmod(0o750)
    config_path = custom_parent / "config.json"
    existing = _write_config(config_path, profile="existing")
    config_path.chmod(0o644)
    original_inode = config_path.stat().st_ino
    added = Config(profile="added", region="eu", api_token="another-example-token")

    service = ConfigService(path=config_path)
    service.save(added)

    assert config_path.stat().st_ino == original_inode
    assert _mode(config_path) == 0o600
    assert _mode(custom_parent) == 0o750
    assert service.load(existing.profile) == existing
    assert service.load(added.profile) == added


@POSIX_ONLY
def test_load_hardens_existing_default_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loading from the default location should harden its directory and file."""
    config_path = tmp_path / ".sccfm-cli" / "config.json"
    config_path.parent.mkdir()
    config_path.parent.chmod(0o755)
    expected = _write_config(config_path)
    config_path.chmod(0o644)
    _use_default_path(monkeypatch, config_path)

    loaded = ConfigService().load(expected.profile)

    assert loaded == expected
    assert _mode(config_path.parent) == 0o700
    assert _mode(config_path) == 0o600


@POSIX_ONLY
def test_save_hardens_existing_default_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saving to the default location should harden its directory and file."""
    config_path = tmp_path / ".sccfm-cli" / "config.json"
    config_path.parent.mkdir()
    config_path.parent.chmod(0o755)
    _write_config(config_path)
    config_path.chmod(0o644)
    _use_default_path(monkeypatch, config_path)

    ConfigService().save(Config(profile="added", region="eu", api_token="example-token-2"))

    assert _mode(config_path.parent) == 0o700
    assert _mode(config_path) == 0o600


def test_non_posix_fallback_preserves_save_and_load_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Platforms without POSIX permissions should still persist configuration."""
    config_path = tmp_path / "config.json"
    expected = Config(profile="default", region="us", api_token="example-token")
    monkeypatch.setattr(
        ConfigService,
        "_supports_posix_permissions",
        staticmethod(lambda: False),
    )

    service = ConfigService(path=config_path)
    service.save(expected)

    assert service.load(expected.profile) == expected
