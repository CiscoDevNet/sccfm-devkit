# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, cast

import pytest
import yaml
from ansible.inventory.data import InventoryData
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template
from plugins.inventory import sccfm as inventory_plugin
from plugins.module_utils.config import Config
from scc_firewall_manager_sdk import Device

_SYNTHETIC_TOKEN = "not-a-secret-sec002"
_DEVICE_NAME = "sec002-device"
_EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "examples"
_E2E_DIR = _EXAMPLES_DIR.parent / "e2e"
_SCCFM_ACTION_GROUP = "group/cisco.sccfm.all"
_EFFECTIVE_TOKEN_VARIABLE = "sccfm_api_token_effective"
_EFFECTIVE_TOKEN_EXPRESSION = (
    "{{ vault_sccfm_api_token | " "default(lookup('env', 'SCCFM_API_TOKEN'), true) }}"
)
_PACKAGED_PLAYBOOK_AUTH_DEFAULTS = {
    "region": "{{ lookup('env', 'SCCFM_REGION') }}",
    "api_token": f"{{{{ {_EFFECTIVE_TOKEN_VARIABLE} }}}}",
}
_EXAMPLES_WITHOUT_SCCFM_API_AUTH = {
    "configure_manager.yml",
    "inventory.sccfm.yml",
    "show_devices.yml",
}
_E2E_VAULT_FILE = "../../../examples/group_vars/all/vault.yml"
_E2E_VAULT_TOKEN_EXPRESSION = "{{ vault_sccfm_api_token }}"
_E2E_LOCAL_AUTH_PLAYBOOK = Path("asa/playbooks/remove_vasa.yml")
_E2E_LOCAL_TOKEN_EXPRESSION = "{{ lookup('env', 'API_TOKEN') }}"
_E2E_NO_AUTH_PLAYBOOKS = {Path("ftd/playbooks/cleanup.yml")}


@dataclass(frozen=True)
class _SyntheticDevice:
    name: str = _DEVICE_NAME
    uid: str = "00000000-0000-0000-0000-000000000002"
    device_type: str = "ASA"
    connectivity_state: str = "ONLINE"
    config_state: str = "SYNCED"
    software_version: str = "1.2.3"


class _RecordingInventoryLoader:
    captured_config: ClassVar[Config | None] = None

    def __init__(self, *, config: Config, limit: int, query: str | None) -> None:
        del limit, query
        type(self).captured_config = config

    def load_devices(self) -> list[Device]:
        return [cast(Device, _SyntheticDevice())]


def _write_inventory_config(path: Path, *, use_environment: bool) -> None:
    if use_environment:
        region = "{{ lookup('env', 'SCCFM_REGION') }}"
        api_token = "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
    else:
        region = "us"
        api_token = _SYNTHETIC_TOKEN

    path.write_text(
        "\n".join(
            (
                "plugin: cisco.sccfm.sccfm",
                f'region: "{region}"',
                f'api_token: "{api_token}"',
                "group: sccfm",
                "group_by_device_type: false",
                "",
            )
        ),
        encoding="utf-8",
    )


def _serialized_inventory(inventory: InventoryData) -> dict[str, Any]:
    group_vars = dict(inventory.groups["sccfm"].vars)
    host_vars = {
        **group_vars,
        **dict(inventory.hosts[_DEVICE_NAME].vars),
    }
    return {
        "_meta": {"hostvars": {_DEVICE_NAME: host_vars}},
        "sccfm": {
            "hosts": [_DEVICE_NAME],
            "vars": group_vars,
        },
    }


@pytest.mark.parametrize("use_environment", [False, True], ids=["config", "environment"])
def test_inventory_auth_token_is_consumed_but_never_exported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    use_environment: bool,
) -> None:
    inventory_path = tmp_path / "inventory.sccfm.yml"
    _write_inventory_config(inventory_path, use_environment=use_environment)
    if use_environment:
        monkeypatch.setenv("SCCFM_REGION", "us")
        monkeypatch.setenv("SCCFM_API_TOKEN", _SYNTHETIC_TOKEN)
    else:
        monkeypatch.delenv("SCCFM_REGION", raising=False)
        monkeypatch.delenv("SCCFM_API_TOKEN", raising=False)

    _RecordingInventoryLoader.captured_config = None
    monkeypatch.setattr(inventory_plugin, "InventoryLoader", _RecordingInventoryLoader)
    inventory = InventoryData()

    plugin = inventory_plugin.InventoryModule()
    plugin.parse(inventory, DataLoader(), str(inventory_path))

    captured_config = _RecordingInventoryLoader.captured_config
    assert captured_config is not None
    assert captured_config.region == "us"
    assert captured_config.api_token == _SYNTHETIC_TOKEN

    payload = _serialized_inventory(inventory)
    json_output = json.dumps(payload, sort_keys=True)
    yaml_output = yaml.safe_dump(payload, sort_keys=True)
    for serialized in (json_output, yaml_output):
        assert "sccfm_api_token" not in serialized
        assert _SYNTHETIC_TOKEN not in serialized

    group_vars = payload["sccfm"]["vars"]
    host_vars = payload["_meta"]["hostvars"][_DEVICE_NAME]
    assert group_vars == {"sccfm_region": "us"}
    sccfm_host_vars = {key: value for key, value in host_vars.items() if key.startswith("sccfm_")}
    assert sccfm_host_vars == {
        "sccfm_config_state": "SYNCED",
        "sccfm_connectivity_state": "ONLINE",
        "sccfm_device_type": "ASA",
        "sccfm_name": _DEVICE_NAME,
        "sccfm_region": "us",
        "sccfm_software_version": "1.2.3",
        "sccfm_uid": "00000000-0000-0000-0000-000000000002",
    }


def test_packaged_api_playbooks_use_safe_vault_over_environment_auth() -> None:
    offenders: dict[str, object] = {}
    checked_examples: set[str] = set()

    for path in sorted(_EXAMPLES_DIR.glob("*.yml")):
        if path.name in _EXAMPLES_WITHOUT_SCCFM_API_AUTH:
            continue

        checked_examples.add(path.name)
        playbook = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(playbook, list):
            offenders[path.name] = "example is not a playbook"
            continue

        for play_number, play in enumerate(playbook, start=1):
            if not isinstance(play, dict):
                offenders[f"{path.name} play {play_number}"] = "play is not a mapping"
                continue
            module_defaults = play.get("module_defaults", {})
            actual = (
                module_defaults.get(_SCCFM_ACTION_GROUP)
                if isinstance(module_defaults, dict)
                else None
            )
            variables = play.get("vars", {})
            effective_token = (
                variables.get(_EFFECTIVE_TOKEN_VARIABLE) if isinstance(variables, dict) else None
            )
            if (
                actual != _PACKAGED_PLAYBOOK_AUTH_DEFAULTS
                or effective_token != _EFFECTIVE_TOKEN_EXPRESSION
            ):
                offenders[f"{path.name} play {play_number}"] = {
                    "module_defaults": actual,
                    _EFFECTIVE_TOKEN_VARIABLE: effective_token,
                }

    assert checked_examples
    assert offenders == {}


def test_e2e_playbooks_use_current_vault_key_except_explicit_local_auth() -> None:
    offenders: dict[str, object] = {}
    checked_vault_playbooks: set[Path] = set()
    checked_local_auth = False
    checked_no_auth: set[Path] = set()

    for path in sorted(_E2E_DIR.glob("*/playbooks/*.yml")):
        relative_path = path.relative_to(_E2E_DIR)
        playbook = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(playbook, list):
            offenders[relative_path.as_posix()] = "example is not a playbook"
            continue

        for play_number, play in enumerate(playbook, start=1):
            offender_key = f"{relative_path.as_posix()} play {play_number}"
            if not isinstance(play, dict):
                offenders[offender_key] = "play is not a mapping"
                continue

            vars_files = play.get("vars_files")
            module_defaults = play.get("module_defaults", {})
            action_group_defaults = (
                module_defaults.get(_SCCFM_ACTION_GROUP)
                if isinstance(module_defaults, dict)
                else None
            )

            if relative_path in _E2E_NO_AUTH_PLAYBOOKS:
                if vars_files is not None or module_defaults:
                    offenders[offender_key] = {
                        "vars_files": vars_files,
                        "module_defaults": module_defaults,
                    }
                checked_no_auth.add(relative_path)
                continue

            if relative_path == _E2E_LOCAL_AUTH_PLAYBOOK:
                variables = play.get("vars", {})
                local_token = (
                    variables.get("sccfm_api_token") if isinstance(variables, dict) else None
                )
                if (
                    vars_files is not None
                    or module_defaults
                    or local_token != _E2E_LOCAL_TOKEN_EXPRESSION
                ):
                    offenders[offender_key] = {
                        "vars_files": vars_files,
                        "module_defaults": module_defaults,
                        "sccfm_api_token": local_token,
                    }
                checked_local_auth = True
                continue

            actual_token = (
                action_group_defaults.get("api_token")
                if isinstance(action_group_defaults, dict)
                else None
            )
            has_vault_file = isinstance(vars_files, list) and _E2E_VAULT_FILE in vars_files
            has_legacy_reference = "{{ sccfm_api_token }}" in path.read_text(encoding="utf-8")
            if (
                not has_vault_file
                or actual_token != _E2E_VAULT_TOKEN_EXPRESSION
                or has_legacy_reference
            ):
                offenders[offender_key] = {
                    "vars_files": vars_files,
                    "api_token": actual_token,
                    "legacy_reference": has_legacy_reference,
                }
            checked_vault_playbooks.add(relative_path)

    assert checked_vault_playbooks
    assert checked_local_auth
    assert checked_no_auth == _E2E_NO_AUTH_PLAYBOOKS
    assert offenders == {}


@pytest.mark.parametrize(
    ("vault_token", "environment_token", "expected"),
    [
        (None, "environment-token", "environment-token"),
        ("", "environment-token", "environment-token"),
        ("vault-token", "environment-token", "vault-token"),
        (None, "", ""),
        ("", "", ""),
    ],
    ids=[
        "undefined-vault",
        "empty-vault",
        "vault-override",
        "both-missing",
        "both-empty",
    ],
)
def test_effective_playbook_token_precedence(
    monkeypatch: pytest.MonkeyPatch,
    vault_token: str | None,
    environment_token: str,
    expected: str,
) -> None:
    monkeypatch.setenv("SCCFM_API_TOKEN", environment_token)
    variables = {} if vault_token is None else {"vault_sccfm_api_token": vault_token}
    templar = Templar(loader=DataLoader(), variables=variables)

    rendered = templar.template(trust_as_template(_EFFECTIVE_TOKEN_EXPRESSION))

    assert rendered == expected
    if not expected:
        with pytest.raises(ValueError, match="api_token is required"):
            Config(region="us", api_token=rendered)


def test_packaged_group_vars_does_not_override_controller_region() -> None:
    variables = yaml.safe_load(
        (_EXAMPLES_DIR / "group_vars" / "all" / "vars.yml").read_text(encoding="utf-8")
    )

    assert variables["sccfm_region"] == _PACKAGED_PLAYBOOK_AUTH_DEFAULTS["region"]
