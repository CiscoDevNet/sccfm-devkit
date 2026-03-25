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

_EXPECTED_TYPE_FILTER = (
    "(deviceType:CDFMC_MANAGED_FTD"
    " OR deviceType:FDM_MANAGED_FTD"
    " OR deviceType:ONPREM_FMC_MANAGED_FTD)"
)


def _ftd_devices() -> list[Device]:
    return [
        Device(
            uid="ftd-uid-1",
            name="ftd-edge-1",
            device_type=EntityType.FDM_MANAGED_FTD,
            software_version="7.2.0",
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
        Device(
            uid="ftd-uid-2",
            name="ftd-edge-2",
            device_type=EntityType.CDFMC_MANAGED_FTD,
            software_version="7.4.1",
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
    ]


def test_should_list_ftd_devices_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """FTD list command should return valid JSON with device-type filter."""
    captured_params: dict[str, Any] = {}
    devices = _ftd_devices()

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured_params["query"] = query
        return DevicePage(count=len(devices), items=devices)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "ftd", "list", "--format", "json"],
    )

    assert result.exit_code == 0
    assert captured_params["query"] == _EXPECTED_TYPE_FILTER

    payload = json.loads(result.output)
    assert len(payload) == 2


def test_should_and_user_query_with_device_type(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """FTD list with --query should AND the user query with the device-type filter."""
    captured_params: dict[str, Any] = {}

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured_params["query"] = query
        return DevicePage(count=0, items=[])

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "ftd", "list", "--query", "name:edge-*"],
    )

    assert result.exit_code == 0
    assert captured_params["query"] == f"(name:edge-*) AND {_EXPECTED_TYPE_FILTER}"


def test_should_display_ftd_devices_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """FTD list command should display formatted table by default."""
    devices = _ftd_devices()

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(devices), items=devices)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)

    result = cli_runner.invoke(cli, ["inventory", "devices", "ftd", "list"])

    assert result.exit_code == 0
    assert "Devices" in result.output
    for device in devices:
        assert device.name in result.output


def test_should_handle_empty_results(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """FTD list command should handle empty results gracefully."""

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=0, items=[])

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "ftd", "list", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == []
