# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from config import Config, base_argument_spec, create_config

from cisco_sccfm_core.models.profile import Profile
from cisco_sccfm_core.services.profile_service import ProfileService


def test_config_should_normalize_region_case_and_legacy_aliases() -> None:
    config = Config(region="AUS", api_token="token-xyz")

    assert config.region == "au"


def test_config_should_reject_unknown_regions() -> None:
    with pytest.raises(ValueError, match="SCCFM region must be one of"):
        Config(region="mars", api_token="token-xyz")


def test_base_argument_spec_should_only_expose_canonical_profile_options() -> None:
    spec = base_argument_spec()

    assert spec == {
        "profile": {"type": "str", "required": False, "default": "default"},
        "config_path": {"type": "path", "required": False},
    }


def test_create_config_should_load_named_profile(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_path = tmp_path / "config.json"
    module = MagicMock()
    module.params = {"profile": "lab", "config_path": str(config_path)}
    monkeypatch.setattr(
        ProfileService,
        "load",
        lambda _service, profile: Profile(
            profile=profile,
            region="eu",
            api_token="profile-token",
        ),
    )

    config = create_config(module)

    assert config == Config(region="eu", api_token="profile-token")
    module.fail_json.assert_not_called()


def test_create_config_should_fail_for_missing_profile(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    module = MagicMock()
    module.params = {"profile": "missing", "config_path": str(tmp_path / "config.json")}
    monkeypatch.setattr(ProfileService, "load", lambda _service, _profile: None)

    with pytest.raises(ValueError, match="profile 'missing' not found"):
        create_config(module)

    assert "sccfm-cli --profile missing configure" in module.fail_json.call_args.kwargs["msg"]
