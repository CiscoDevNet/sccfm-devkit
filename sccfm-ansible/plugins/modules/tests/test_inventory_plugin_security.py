# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, cast

import pytest
import yaml
from ansible.errors import AnsibleParserError
from ansible.inventory.data import InventoryData
from ansible.parsing.dataloader import DataLoader
from plugins.inventory import sccfm as inventory_plugin
from plugins.module_utils.config import Config
from scc_firewall_manager_sdk import Device

from cisco_sccfm_core.models.profile import Profile
from cisco_sccfm_core.services.profile_service import ProfileService

_SYNTHETIC_TOKEN = "not-a-secret-sec002"
_DEVICE_NAME = "sec002-device"
_EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "examples"
_E2E_DIR = _EXAMPLES_DIR.parent / "e2e"
_SCCFM_ACTION_GROUP = "group/cisco.sccfm.all"


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


def _write_profile(config_path: Path) -> None:
    ProfileService(path=config_path).save(
        Profile(profile="default", region="us", api_token=_SYNTHETIC_TOKEN)
    )


def _write_inventory_config(path: Path, config_path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "plugin": "cisco.sccfm.sccfm",
                "profile": "default",
                "config_path": str(config_path),
                "group": "sccfm",
                "group_by_device_type": False,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _serialized_inventory(inventory: InventoryData) -> dict[str, object]:
    group_vars = dict(inventory.groups["sccfm"].vars)
    host_vars = {**group_vars, **dict(inventory.hosts[_DEVICE_NAME].vars)}
    return {
        "_meta": {"hostvars": {_DEVICE_NAME: host_vars}},
        "sccfm": {"hosts": [_DEVICE_NAME], "vars": group_vars},
    }


def test_inventory_profile_token_is_consumed_but_never_exported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "profiles.json"
    inventory_path = tmp_path / "inventory.sccfm.yml"
    _write_profile(config_path)
    _write_inventory_config(inventory_path, config_path)

    _RecordingInventoryLoader.captured_config = None
    monkeypatch.setattr(
        inventory_plugin.ProfileService,
        "load",
        lambda _service, profile: Profile(
            profile=profile,
            region="us",
            api_token=_SYNTHETIC_TOKEN,
        ),
    )
    monkeypatch.setattr(inventory_plugin, "InventoryLoader", _RecordingInventoryLoader)
    inventory = InventoryData()

    plugin = inventory_plugin.InventoryModule()
    plugin.parse(inventory, DataLoader(), str(inventory_path))

    captured_config = _RecordingInventoryLoader.captured_config
    assert captured_config is not None
    assert captured_config.region == "us"
    assert captured_config.api_token == _SYNTHETIC_TOKEN

    payload = _serialized_inventory(inventory)
    serialized = json.dumps(payload, sort_keys=True)
    assert "sccfm_api_token" not in serialized
    assert _SYNTHETIC_TOKEN not in serialized

    group_vars = cast(dict[str, object], cast(dict[str, object], payload["sccfm"])["vars"])
    assert group_vars == {"sccfm_profile": "default", "sccfm_region": "us"}


def test_inventory_reports_missing_devkit_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory_path = tmp_path / "inventory.sccfm.yml"
    _write_inventory_config(inventory_path, tmp_path / "profiles.json")
    monkeypatch.setattr(
        inventory_plugin,
        "_DEPENDENCY_IMPORT_ERROR",
        ImportError("cisco_sccfm_core is unavailable"),
    )

    with pytest.raises(AnsibleParserError, match="cisco-sccfm-devkit must be installed"):
        inventory_plugin.InventoryModule().parse(
            InventoryData(),
            DataLoader(),
            str(inventory_path),
        )


def test_packaged_examples_use_profiles_without_sccfm_api_tokens() -> None:
    checked_playbooks = 0
    offenders: dict[str, object] = {}

    for path in sorted(_EXAMPLES_DIR.glob("*.yml")):
        content = path.read_text(encoding="utf-8")
        if "SCCFM_API_TOKEN" in content or "vault_sccfm_api_token" in content:
            offenders[path.name] = "contains legacy SCCFM API token authentication"
            continue

        playbook = yaml.safe_load(content)
        if not isinstance(playbook, list):
            continue
        for play_number, play in enumerate(playbook, start=1):
            if not isinstance(play, dict) or "module_defaults" not in play:
                continue
            checked_playbooks += 1
            actual = play["module_defaults"].get(_SCCFM_ACTION_GROUP)
            if actual != {"profile": "default"}:
                offenders[f"{path.name} play {play_number}"] = actual

    assert checked_playbooks
    assert offenders == {}


def test_e2e_playbooks_use_profiles_without_sccfm_api_tokens() -> None:
    offenders: dict[str, object] = {}
    checked_playbooks = 0

    for path in sorted(_E2E_DIR.glob("*/playbooks/*.yml")):
        content = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(_E2E_DIR).as_posix()
        if "SCCFM_API_TOKEN" in content or "vault_sccfm_api_token" in content:
            offenders[relative_path] = "contains legacy SCCFM API token authentication"
            continue

        playbook = yaml.safe_load(content)
        if not isinstance(playbook, list):
            offenders[relative_path] = "playbook is not a list"
            continue
        for play_number, play in enumerate(playbook, start=1):
            checked_playbooks += 1
            module_defaults = play.get("module_defaults", {})
            actual = module_defaults.get(_SCCFM_ACTION_GROUP)
            if not module_defaults and relative_path in {
                "asa/playbooks/remove_vasa.yml",
                "ftd/playbooks/cleanup.yml",
            }:
                continue
            if actual != {"profile": "default"}:
                offenders[f"{relative_path} play {play_number}"] = actual

    assert checked_playbooks
    assert offenders == {}
