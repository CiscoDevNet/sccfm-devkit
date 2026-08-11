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
from plugins.inventory import sccfm as inventory_plugin
from plugins.module_utils.config import Config
from scc_firewall_manager_sdk import Device

_SYNTHETIC_TOKEN = "not-a-secret-sec002"
_DEVICE_NAME = "sec002-device"
_EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "examples"


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


def test_packaged_examples_do_not_depend_on_inventory_token_variable() -> None:
    offenders = [
        path.name
        for path in sorted(_EXAMPLES_DIR.glob("*.yml"))
        if "{{ sccfm_api_token }}" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
