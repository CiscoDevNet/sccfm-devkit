# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for Ansible E2E credential handling."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_ONBOARD_PLAYBOOK = (
    _REPOSITORY_ROOT / "sccfm-ansible" / "e2e" / "asa" / "playbooks" / "onboard_vasa.yml"
)
_VAULT_EXAMPLE = (
    _REPOSITORY_ROOT / "sccfm-ansible" / "examples" / "group_vars" / "all" / "vault.yml.example"
)


def _load_single_play() -> tuple[dict[str, Any], str]:
    content = _ONBOARD_PLAYBOOK.read_text(encoding="utf-8")
    plays = yaml.safe_load(content)

    assert isinstance(plays, list)
    assert len(plays) == 1
    assert isinstance(plays[0], dict)
    return cast(dict[str, Any], plays[0]), content


def test_ansible_vasa_onboarding_uses_vaulted_device_password() -> None:
    play, content = _load_single_play()
    onboard_task = next(
        task["cisco.sccfm.onboard_asa"]
        for task in play["tasks"]
        if "cisco.sccfm.onboard_asa" in task
    )

    assert "../../../examples/group_vars/all/vault.yml" in play["vars_files"]
    assert onboard_task["password"] == "{{ vault_vasa_password }}"
    assert "lookup('env', 'VASA_PASSWORD')" not in content


def test_vault_example_declares_vasa_password() -> None:
    vault_example = yaml.safe_load(_VAULT_EXAMPLE.read_text(encoding="utf-8"))

    assert isinstance(vault_example, dict)
    assert "vault_vasa_password" in vault_example
