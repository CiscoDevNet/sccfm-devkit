# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

import pytest
from config import Config
from plugins.module_utils import dependencies


class _ModuleFailure(RuntimeError):
    """Capture a synthetic Ansible module failure."""

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(payload["msg"])
        self.payload = payload


class _FakeModule:
    def fail_json(self, **kwargs: Any) -> None:
        raise _ModuleFailure(kwargs)


def test_config_should_normalize_region_case_and_legacy_aliases() -> None:
    config = Config(region="AUS", api_token="token-xyz")

    assert config.region == "au"


def test_config_should_reject_unknown_regions() -> None:
    with pytest.raises(ValueError, match="SCCFM region must be one of"):
        Config(region="mars", api_token="token-xyz")


def test_missing_dependency_uses_actionable_ansible_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        dependencies,
        "_IMPORT_ERRORS",
        [("cisco_sccfm_core", "synthetic import traceback")],
    )

    with pytest.raises(_ModuleFailure) as exc_info:
        dependencies.ensure_required_dependencies(_FakeModule())

    payload = exc_info.value.payload
    assert dependencies._PAIRED_DEVKIT_REQUIREMENT in payload["msg"]
    assert dependencies._PAIRED_DEVKIT_REQUIREMENT.startswith("cisco-sccfm-devkit==")
    assert "cisco_sccfm_core" not in payload["msg"]
    assert payload["exception"] == "synthetic import traceback"
