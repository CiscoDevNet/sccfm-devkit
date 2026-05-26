# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import (
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
)

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services import InventoryService


def _asa_devices() -> list[Device]:
    return [
        Device(
            uid="asa-uid-1",
            name="branch-fw-1",
            device_type=EntityType.ASA,
            software_version="9.16.1",
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
        Device(
            uid="asa-uid-2",
            name="branch-fw-2",
            device_type=EntityType.ASA,
            software_version="9.18.2",
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
    ]


def test_should_list_asa_devices_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """ASA list command should return valid JSON with device-type filter."""
    captured_params: dict[str, Any] = {}
    devices = _asa_devices()

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured_params["query"] = query
        return DevicePage(count=len(devices), items=devices)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list", "--format", "json"],
    )

    assert result.exit_code == 0
    assert captured_params["query"] == "deviceType:ASA"

    payload = json.loads(result.output)
    assert len(payload) == 2


def test_should_and_user_query_with_device_type(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """ASA list with --query should AND the user query with the device-type filter."""
    captured_params: dict[str, Any] = {}

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured_params["query"] = query
        return DevicePage(count=0, items=[])

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list", "--query", "name:branch-*"],
    )

    assert result.exit_code == 0
    assert captured_params["query"] == "(name:branch-*) AND deviceType:ASA"


def test_should_display_asa_devices_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """ASA list command should display formatted table by default."""
    devices = _asa_devices()

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(devices), items=devices)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)

    result = cli_runner.invoke(cli, ["inventory", "devices", "asa", "list"])

    assert result.exit_code == 0
    assert "Devices" in result.output
    assert "Page:" in result.output
    for device in devices:
        assert device.name in result.output


def test_should_handle_empty_results(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """ASA list command should handle empty results gracefully."""

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=0, items=[])

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == []
