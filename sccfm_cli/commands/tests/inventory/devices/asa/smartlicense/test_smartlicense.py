# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import CdoCliResult, Device, DevicePage, EntityType

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services import AsaCommandLineService, InventoryService


def test_should_apply_smart_license_to_virtual_asas_with_json_output(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
) -> None:
    """Smart license command should apply license to virtual ASAs and return JSON."""
    captured_inventory_params: dict[str, Any] = {}
    captured_cli_params: dict[str, Any] = {}
    expected_token = "test-token-123"
    expected_feature_tier = "standard"
    expected_throughput_level = "1G"
    expected_device_uids = ["uid-1", "uid-2"]

    # Make devices virtual ASAs
    for device in sample_devices:
        device.hardware_model = "ASAv"

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
            "smartlicense",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--token",
            expected_token,
            "--feature-tier",
            expected_feature_tier,
            "--throughput-level",
            expected_throughput_level,
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Verify service was called with correct parameters
    assert captured_cli_params["device_uids"] == expected_device_uids

    # Verify script contains the expected commands
    script_commands = captured_cli_params["asa_commands"]
    assert "license smart" in script_commands
    assert f"feature tier {expected_feature_tier}" in script_commands
    assert f"throughput level {expected_throughput_level}" in script_commands
    assert f"license smart register idtoken {expected_token}" in script_commands
    assert "write memory" in script_commands

    # Verify JSON output
    payload = json.loads(result.output)
    assert len(payload) == 2
    expected_payload = [result.model_dump(mode="json") for result in sample_cli_results]
    assert payload == expected_payload


def test_should_apply_smart_license_to_hardware_asas_without_throughput_level(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
) -> None:
    """Smart license command should apply license to hardware ASAs without throughput level."""
    captured_cli_params: dict[str, Any] = {}
    expected_token = "test-token-456"
    expected_feature_tier = "standard"

    # Make devices hardware ASAs
    for device in sample_devices:
        device.hardware_model = "ASA5506-X"

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
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
            "smartlicense",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--token",
            expected_token,
            "--feature-tier",
            expected_feature_tier,
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Verify script does NOT contain throughput level command
    script_commands = captured_cli_params["asa_commands"]
    assert "license smart" in script_commands
    assert f"feature tier {expected_feature_tier}" in script_commands
    assert "throughput level" not in " ".join(script_commands)
    assert f"license smart register idtoken {expected_token}" in script_commands
    assert "write memory" in script_commands


def test_should_display_smart_license_results_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
) -> None:
    """Smart license command should display formatted table by default."""
    expected_token = "test-token-789"
    expected_feature_tier = "standard"

    # Make devices hardware ASAs
    for device in sample_devices:
        device.hardware_model = "ASA5515-X"

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
            "smartlicense",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--token",
            expected_token,
            "--feature-tier",
            expected_feature_tier,
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert result.output is not None
    output_text = str(result.output)

    # Verify table contains expected content
    assert "Executed script:" in output_text
    assert "license smart" in output_text
    for device in sample_devices:
        assert device.name in output_text
        if device.uid:
            assert device.uid in output_text


def test_should_filter_devices_by_query(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
) -> None:
    """Smart license command should pass query filter to inventory service."""
    captured_params: dict[str, Any] = {}
    expected_query = "deviceType:ASA AND name:firewall*"
    expected_limit = 10
    expected_offset = 5

    # Make devices hardware ASAs
    for device in sample_devices:
        device.hardware_model = "ASA5525-X"

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
            "smartlicense",
            "--query",
            expected_query,
            "--limit",
            str(expected_limit),
            "--offset",
            str(expected_offset),
            "--token",
            "test-token",
            "--feature-tier",
            "standard",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured_params["query"] == f"{expected_query} AND deviceType:ASA"
    assert captured_params["limit"] == expected_limit
    assert captured_params["offset"] == expected_offset


def test_should_fail_when_throughput_level_specified_for_hardware_asa(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """Smart license command should fail when throughput level specified for hardware ASA."""
    # Make devices hardware ASAs
    for device in sample_devices:
        device.hardware_model = "ASA5516-X"

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def stub_asa_cli_init(self: AsaCommandLineService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaCommandLineService, "__init__", stub_asa_cli_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "smartlicense",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--token",
            "test-token",
            "--feature-tier",
            "standard",
            "--throughput-level",
            "1G",
        ],
    )

    assert result.exit_code != 0
    assert "not virtual ASAs" in result.output


def test_should_fail_without_query_or_device_uids(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
) -> None:
    """Smart license command should fail when neither query nor device UIDs provided."""
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "smartlicense",
            "--token",
            "test-token",
            "--feature-tier",
            "standard",
        ],
    )

    assert result.exit_code != 0
    assert "Provide exactly one of --query or --device-uids" in result.output


def test_should_fail_with_both_query_and_device_uids(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
) -> None:
    """Smart license command should fail when both query and device UIDs provided."""
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "smartlicense",
            "--query",
            "deviceType:ASA",
            "-u",
            "uid-1",
            "--token",
            "test-token",
            "--feature-tier",
            "standard",
        ],
    )

    assert result.exit_code != 0
    assert "Provide exactly one of --query or --device-uids" in result.output


def test_should_display_usage_on_validation_error(
    cli_runner: CliRunner, default_config: Config
) -> None:
    """Validation errors should keep Click's usage/help output intact."""
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "smartlicense",
            "--token",
            "token-1",
            "--feature-tier",
            "standard",
            "--query",
            "name:asa",
            "--device-uids",
            "uid-1",
        ],
    )

    assert result.exit_code == 2
    assert "Usage:" in result.output
    assert "inventory devices asa smartlicense" in result.output
    assert "Provide exactly one of --query or --device-uids." in result.output


def test_check_mode_should_report_targets_without_requiring_token_or_executing(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """smartlicense --check should only resolve targets and skip CLI execution."""
    captured_params: dict[str, Any] = {}
    execute_called = {"called": False}
    asa_device = Device(uid="uid-asa-1", name="edge-asa", device_type=EntityType.ASA)

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured_params["query"] = query
        return DevicePage(count=1, items=[asa_device])

    def fake_execute_cli(
        self: AsaCommandLineService, *, device_uids: list[str], asa_commands: list[str]
    ) -> list[CdoCliResult]:
        execute_called["called"] = True
        return []

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
            "smartlicense",
            "--query",
            "name:edge-*",
            "--check",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured_params["query"] == "name:edge-* AND deviceType:ASA"
    assert execute_called["called"] is False

    payload = json.loads(result.output)
    assert payload["operation"] == "smartlicense"
    assert payload["can_proceed"] is True
    assert payload["reason"] == "targets_found"
    assert payload["matched_devices"] == 1
    assert payload["devices"][0]["uid"] == "uid-asa-1"
    assert payload["devices"][0]["device_type"] == "ASA"
