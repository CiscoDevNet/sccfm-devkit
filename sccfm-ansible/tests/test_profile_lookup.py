# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from ansible.errors import AnsibleError

from cisco_sccfm_core.models.profile import Profile
from cisco_sccfm_core.services.profile_service import ProfileService

_PLUGIN_PATH = Path(__file__).resolve().parent.parent / "plugins" / "lookup" / "profile.py"
_SPEC = importlib.util.spec_from_file_location("sccfm_profile_lookup", _PLUGIN_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
LookupModule = _MODULE.LookupModule


def _lookup(config_path: Path, field: str = "api_token") -> LookupModule:
    lookup = LookupModule()
    lookup.set_options = lambda **kwargs: None  # type: ignore[method-assign]
    lookup.get_option = lambda name: {  # type: ignore[method-assign]
        "field": field,
        "config_path": str(config_path),
    }[name]
    return lookup


def test_should_read_profile_field(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    ProfileService(config_path).save(Profile(profile="lab", region="eu", api_token="test-token"))

    assert _lookup(config_path).run(["lab"]) == ["test-token"]
    assert _lookup(config_path, field="region").run(["lab"]) == ["eu"]


def test_should_fail_for_missing_profile(tmp_path: Path) -> None:
    with pytest.raises(AnsibleError, match="profile 'missing' not found"):
        _lookup(tmp_path / "config.json").run(["missing"])
