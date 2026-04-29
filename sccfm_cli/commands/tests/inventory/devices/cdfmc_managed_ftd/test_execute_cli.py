"""Tests for the ``sccfm_cli inventory devices cdfmc-managed-ftd cli execute`` command."""

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import ConfigState, ConnectivityState, Device, DevicePage, EntityType

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.models.ftd_cli_result import FtdBulkCliResult, FtdDeviceCliResponse
from sccfm_core.services import InventoryService
from sccfm_core.services.inventory.ftd_cli_service import FtdCommandLineService

FMC_UID_1 = "09590f30-8cb7-11f0-a508-8e9f8a6273f4"
FMC_UID_2 = "09590f30-8cb7-11f0-a508-8e9f8a6273f5"


def _sample_devices() -> list[Device]:
    return [
        Device(
            uid="uid-1",
            name="branch-ftd-01",
            deviceType=EntityType.CDFMC_MANAGED_FTD,
            connectivityState=ConnectivityState.ONLINE,
            configState=ConfigState.SYNCED,
        ),
        Device(
            uid="uid-2",
            name="branch-ftd-02",
            deviceType=EntityType.CDFMC_MANAGED_FTD,
            connectivityState=ConnectivityState.ONLINE,
            configState=ConfigState.SYNCED,
        ),
    ]


def _sample_result(command: str = "show version") -> FtdBulkCliResult:
    return FtdBulkCliResult(
        command=command,
        device_responses=[
            FtdDeviceCliResponse(
                device_uuid=FMC_UID_1,
                device_name="branch-ftd-01",
                response="Cisco Firepower Version 7.6.0",
                is_error=False,
            ),
            FtdDeviceCliResponse(
                device_uuid=FMC_UID_2,
                device_name="branch-ftd-02",
                response="Cisco Firepower Version 7.6.0",
                is_error=False,
            ),
        ],
    )


def _stub_ftd_cli_init(self: FtdCommandLineService, config: Any) -> None:
    return None


def test_should_return_cli_results_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    sample_devices = _sample_devices()
    captured_cli_params: dict[str, Any] = {}

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_execute_cli(
        self: FtdCommandLineService, *, devices: list[Device], command: str
    ) -> FtdBulkCliResult:
        captured_cli_params["device_uids"] = [device.uid for device in devices]
        captured_cli_params["command"] = command
        return _sample_result(command=command)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(FtdCommandLineService, "execute_cli", fake_execute_cli)
    monkeypatch.setattr(FtdCommandLineService, "__init__", _stub_ftd_cli_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "cdfmc-managed-ftd",
            "cli",
            "execute",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--command",
            "show version",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured_cli_params["device_uids"] == ["uid-1", "uid-2"]
    assert captured_cli_params["command"] == "show version"

    payload = json.loads(result.output)
    assert payload["command"] == "show version"
    assert len(payload["device_responses"]) == 2
    assert payload["device_responses"][0]["device_name"] == "branch-ftd-01"


def test_should_display_cli_results_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    sample_devices = _sample_devices()

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_execute_cli(
        self: FtdCommandLineService, *, devices: list[Device], command: str
    ) -> FtdBulkCliResult:
        return _sample_result(command=command)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(FtdCommandLineService, "execute_cli", fake_execute_cli)
    monkeypatch.setattr(FtdCommandLineService, "__init__", _stub_ftd_cli_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "cdfmc-managed-ftd",
            "cli",
            "execute",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--command",
            "show version",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "Command: show version" in result.output
    assert "branch-ftd-01" in result.output
    assert "Device UUID" in result.output


def test_should_filter_devices_by_query_and_execute_cli_on_devices(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    sample_devices = _sample_devices()
    captured_params: dict[str, Any] = {}
    query = "name:branch*"
    expected_limit = 10
    expected_offset = 5

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured_params["limit"] = limit
        captured_params["offset"] = offset
        captured_params["query"] = query
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_execute_cli(
        self: FtdCommandLineService, *, devices: list[Device], command: str
    ) -> FtdBulkCliResult:
        return _sample_result(command=command)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(FtdCommandLineService, "execute_cli", fake_execute_cli)
    monkeypatch.setattr(FtdCommandLineService, "__init__", _stub_ftd_cli_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "cdfmc-managed-ftd",
            "cli",
            "execute",
            "--query",
            query,
            "--limit",
            str(expected_limit),
            "--offset",
            str(expected_offset),
            "--command",
            "show failover",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert (
        captured_params["query"] == f"{query} AND deviceType:{EntityType.CDFMC_MANAGED_FTD.value}"
    )
    assert captured_params["limit"] == expected_limit
    assert captured_params["offset"] == expected_offset


def test_check_mode_should_report_targets_without_executing_cli(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    captured_params: dict[str, Any] = {}
    execute_called = {"called": False}
    ftd_device = Device(
        uid="uid-ftd-1",
        name="edge-ftd",
        deviceType=EntityType.CDFMC_MANAGED_FTD,
        connectivityState=ConnectivityState.ONLINE,
    )

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured_params["query"] = query
        return DevicePage(count=1, items=[ftd_device])

    def fake_execute_cli(
        self: FtdCommandLineService, *, devices: list[Device], command: str
    ) -> FtdBulkCliResult:
        execute_called["called"] = True
        return _sample_result(command=command)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(FtdCommandLineService, "execute_cli", fake_execute_cli)
    monkeypatch.setattr(FtdCommandLineService, "__init__", _stub_ftd_cli_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "cdfmc-managed-ftd",
            "cli",
            "execute",
            "--query",
            "name:edge*",
            "--check",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured_params["query"] == "name:edge* AND deviceType:CDFMC_MANAGED_FTD"
    assert execute_called["called"] is False

    payload = json.loads(result.output)
    assert payload["operation"] == "FTD CLI execution"
    assert payload["can_proceed"] is True
    assert payload["reason"] == "targets_found"
    assert payload["matched_devices"] == 1
    assert payload["devices"][0]["uid"] == "uid-ftd-1"
    assert payload["devices"][0]["device_type"] == "CDFMC_MANAGED_FTD"


def test_check_mode_should_handle_empty_sdk_page_items(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    execute_called = {"called": False}

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=0, items=None)

    def fake_execute_cli(
        self: FtdCommandLineService, *, devices: list[Device], command: str
    ) -> FtdBulkCliResult:
        execute_called["called"] = True
        return _sample_result(command=command)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(FtdCommandLineService, "execute_cli", fake_execute_cli)
    monkeypatch.setattr(FtdCommandLineService, "__init__", _stub_ftd_cli_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "cdfmc-managed-ftd",
            "cli",
            "execute",
            "--query",
            "name:missing*",
            "--check",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert execute_called["called"] is False
    payload = json.loads(result.output)
    assert payload["can_proceed"] is False
    assert payload["reason"] == "no_targets_matched"
    assert payload["matched_devices"] == 0
    assert payload["devices"] == []
