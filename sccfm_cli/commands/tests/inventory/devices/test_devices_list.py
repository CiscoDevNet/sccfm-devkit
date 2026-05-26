# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import Device, DevicePage

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services import InventoryService


def test_should_return_devices_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """Devices list command should return valid JSON when format is json."""
    captured_params: dict[str, Any] = {}
    expected_limit = 1
    expected_offset = 0
    expected_query = "edge"

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured_params["limit"] = limit
        captured_params["offset"] = offset
        captured_params["query"] = query
        return DevicePage(count=len(sample_devices), items=sample_devices)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "list",
            "--limit",
            str(expected_limit),
            "--query",
            expected_query,
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured_params["limit"] == expected_limit
    assert captured_params["offset"] == expected_offset
    assert captured_params["query"] == expected_query

    payload = json.loads(result.output)
    assert len(payload) == 2
    expected_payload = [device.to_dict() for device in sample_devices]
    assert payload == expected_payload


def test_should_display_devices_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """Devices list command should display formatted table by default."""

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)

    result = cli_runner.invoke(cli, ["inventory", "devices", "list"])

    assert result.exit_code == 0
    assert "Devices" in result.output
    assert "Page:" in result.output
    for sample_device in sample_devices:
        assert sample_device.name in result.output
