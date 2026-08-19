# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_PLAYBOOKS_DIR = _REPOSITORY_ROOT / "cisco_sccfm_cli" / "e2e" / "playbooks"
_PROFILE = "default"


def _load_playbook(filename: str) -> tuple[dict[str, Any], str]:
    path = _PLAYBOOKS_DIR / filename
    content = path.read_text(encoding="utf-8")
    plays = yaml.safe_load(content)

    assert isinstance(plays, list)
    assert len(plays) == 1
    assert isinstance(plays[0], dict)
    return cast(dict[str, Any], plays[0]), content


def test_cli_vasa_onboarding_uses_default_profile() -> None:
    play, content = _load_playbook("onboard_vasa.yml")
    module_defaults = play["module_defaults"]["group/cisco.sccfm.all"]

    assert module_defaults == {"profile": _PROFILE}
    assert play["vars"]["profile_region"] == (
        "{{ lookup('cisco.sccfm.profile', 'default', field='region') }}"
    )
    assert "api_token" not in content


def test_cli_vasa_cleanup_uses_default_profile_lookup() -> None:
    play, content = _load_playbook("remove_vasa.yml")
    authorizations = [
        task["ansible.builtin.uri"]["headers"]["Authorization"]
        for task in play["tasks"]
        if "ansible.builtin.uri" in task
    ]

    assert play["vars"]["profile_token"] == (
        "{{ lookup('cisco.sccfm.profile', 'default', field='api_token') }}"
    )
    assert authorizations == ["Bearer {{ profile_token }}"] * 2
    assert "vault_sccfm_api_token" not in content
