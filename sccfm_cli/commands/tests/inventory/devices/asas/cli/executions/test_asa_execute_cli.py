from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import CdoCliResult, Device, DevicePage

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services import AsaCommandLineService, InventoryService


def test_should_return_cli_results_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
) -> None:
    """ASA execute CLI command should return valid JSON when format is json."""
    captured_inventory_params: dict[str, Any] = {}
    captured_cli_params: dict[str, Any] = {}
    expected_script = "show version"
    expected_device_uids = ["uid-1", "uid-2"]

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured_inventory_params["limit"] = limit
        captured_inventory_params["offset"] = offset
        captured_inventory_params["query"] = query
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_execute_cli(
        self: AsaCommandLineService, *, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        captured_cli_params["device_uids"] = device_uids
        captured_cli_params["asa_commands"] = asa_commands
        return sample_cli_results

    def stub_asa_cli_init(self: AsaCommandLineService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)
    monkeypatch.setattr(AsaCommandLineService, "__init__", stub_asa_cli_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "cli",
            "execute",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--script",
            expected_script,
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Verify service was called with correct parameters
    assert captured_cli_params["device_uids"] == expected_device_uids
    assert captured_cli_params["asa_commands"] == [expected_script]

    # Verify JSON output
    payload = json.loads(result.output)
    assert len(payload) == 2
    expected_payload = [result.model_dump(mode="json") for result in sample_cli_results]
    assert payload == expected_payload


def test_should_display_cli_results_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
) -> None:
    """ASA execute CLI command should display formatted table by default."""
    expected_script = "show version"

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_execute_cli(
        self: AsaCommandLineService, *, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        return sample_cli_results

    def stub_asa_cli_init(self: AsaCommandLineService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)
    monkeypatch.setattr(AsaCommandLineService, "__init__", stub_asa_cli_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "cli",
            "execute",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--script",
            expected_script,
        ],
    )

    assert result.exit_code == 0
    assert result.output is not None
    output_text = str(result.output)
    assert "Executed script:" in output_text
    assert expected_script in output_text
    for device in sample_devices:
        assert device.name in output_text
        if device.uid:
            assert device.uid in output_text


def test_should_filter_devices_by_query_and_execute_cli_on_devices(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
) -> None:
    """ASA execute CLI command should pass query filter to inventory service."""
    captured_params: dict[str, Any] = {}
    query = "name:burak"
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
        self: AsaCommandLineService, *, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        return sample_cli_results

    def stub_asa_cli_init(self: AsaCommandLineService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)
    monkeypatch.setattr(AsaCommandLineService, "__init__", stub_asa_cli_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "cli",
            "execute",
            "--query",
            query,
            "--limit",
            str(expected_limit),
            "--offset",
            str(expected_offset),
            "--script",
            "show version",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured_params["query"] == f"{query} AND deviceType:ASA"
    assert captured_params["limit"] == expected_limit
    assert captured_params["offset"] == expected_offset
