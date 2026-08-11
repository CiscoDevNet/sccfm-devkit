# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cisco_sccfm_scripts import verify_clean_controller as verifier


def test_discovery_parser_accepts_only_cisco_sccfm_plugins() -> None:
    raw = json.dumps(
        {
            "cisco.sccfm.second_plugin": "Second",
            "cisco.sccfm.first_plugin": "First",
        }
    )

    assert verifier._discovered_plugins(raw, "module") == {
        "cisco.sccfm.first_plugin": "First",
        "cisco.sccfm.second_plugin": "Second",
    }


@pytest.mark.parametrize("raw", ["not-json", "{}", '{"other.collection.plugin": "Bad"}'])
def test_discovery_parser_rejects_invalid_results(raw: str) -> None:
    with pytest.raises(verifier.CleanControllerVerificationError):
        verifier._discovered_plugins(raw, "module")


def test_controller_isolates_user_state_and_sccfm_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCCFM_API_TOKEN", "synthetic-secret")
    monkeypatch.setenv("SCCFM_REGION", "us")
    monkeypatch.setenv("SCCFM_CONFIG", "/not/used")
    monkeypatch.setenv("ANSIBLE_VAULT_PASSWORD_FILE", "/not/used")
    monkeypatch.setenv("PYTHONUSERBASE", "/not/used")
    controller = verifier._create_controller(tmp_path)

    assert not any(name.startswith("SCCFM_") for name in controller.environment)
    assert "ANSIBLE_VAULT_PASSWORD_FILE" not in controller.environment
    assert "PYTHONUSERBASE" not in controller.environment
    assert controller.environment["PYTHONNOUSERSITE"] == "1"
    assert Path(controller.environment["HOME"]).parent == tmp_path
    assert Path(controller.environment["XDG_CONFIG_HOME"]).parent == tmp_path
    assert controller.environment["ANSIBLE_COLLECTIONS_PATH"] == str(controller.collections)
