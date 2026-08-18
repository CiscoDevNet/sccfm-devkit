# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from cisco_sccfm_cli.models import Config
from cisco_sccfm_cli.services import ConfigService
from cisco_sccfm_core.models.profile import Profile
from cisco_sccfm_core.services.profile_service import ProfileService


def test_cli_aliases_resolve_to_the_core_profile_types() -> None:
    """The CLI Config/ConfigService names are re-exports of the core profile types."""
    assert Config is Profile
    assert ConfigService is ProfileService


def test_should_save_and_load_config_through_the_cli_alias(tmp_path: Path) -> None:
    """ConfigService should persist and retrieve configuration."""
    config_path = tmp_path / "config.json"
    service = ConfigService(path=config_path)

    expected = Config(profile="default", region="us", api_token="secret-token")
    service.save(expected)

    loaded = service.load("default")
    assert loaded == expected
