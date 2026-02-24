from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import AsaCompatibleVersion, Device, DevicePage

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.models.asa_upgrade_version import AsaGroupCompatibleVersions
from sccfm_core.services import InventoryService
from sccfm_core.services.inventory import AsaUpgradeVersionService


def _sample_group_versions() -> AsaGroupCompatibleVersions:
    v1 = AsaCompatibleVersion(
        softwareVersion="9.18.4",
        asdmVersion="7.18(1.152)",
        softwareImageUrl="https://example.com/asa918.bin",
        asdmImageUrl="https://example.com/asdm718.bin",
    )
    v2 = AsaCompatibleVersion(
        softwareVersion="9.16.4",
        asdmVersion="7.16(1.150)",
        softwareImageUrl="https://example.com/asa916.bin",
        asdmImageUrl="https://example.com/asdm716.bin",
    )
    return AsaGroupCompatibleVersions(
        per_device={
            "uid-1": [v1, v2],
            "uid-2": [v1],
        },
        common_versions=[v1],
    )


def test_should_return_group_json_without_per_device_by_default(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """Multi-device JSON should show common_versions only (no per_device) by default."""
    captured_params: dict[str, Any] = {}
    group_versions = _sample_group_versions()

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_get_compatible_versions(
        self: AsaUpgradeVersionService, *, device_uids: list[str]
    ) -> AsaGroupCompatibleVersions:
        captured_params["device_uids"] = device_uids
        return group_versions

    def stub_upgrade_init(self: AsaUpgradeVersionService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(
        AsaUpgradeVersionService, "get_compatible_versions", fake_get_compatible_versions
    )
    monkeypatch.setattr(AsaUpgradeVersionService, "__init__", stub_upgrade_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "upgrade",
            "compatible-versions",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured_params["device_uids"] == ["uid-1", "uid-2"]

    payload = json.loads(result.output)
    assert payload["device_count"] == 2
    assert len(payload["common_versions"]) == 1
    assert payload["common_versions"][0]["software_version"] == "9.18.4"
    assert "per_device" not in payload


def test_should_include_per_device_in_json_when_flag_set(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """Multi-device JSON should include per_device when --per-device flag is set."""
    group_versions = _sample_group_versions()

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_get_compatible_versions(
        self: AsaUpgradeVersionService, *, device_uids: list[str]
    ) -> AsaGroupCompatibleVersions:
        return group_versions

    def stub_upgrade_init(self: AsaUpgradeVersionService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(
        AsaUpgradeVersionService, "get_compatible_versions", fake_get_compatible_versions
    )
    monkeypatch.setattr(AsaUpgradeVersionService, "__init__", stub_upgrade_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "upgrade",
            "compatible-versions",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--per-device",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    payload = json.loads(result.output)
    assert payload["device_count"] == 2
    assert "per_device" in payload
    assert "uid-1" in payload["per_device"]
    assert "uid-2" in payload["per_device"]


def test_should_return_flat_json_for_single_device(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Single-device JSON should return a flat list without group wrapper."""
    single_device = Device(uid="uid-1", name="branch-asa-01", deviceType="ASA")
    v1 = AsaCompatibleVersion(
        softwareVersion="9.18.4",
        asdmVersion="7.18(1.152)",
        softwareImageUrl="https://example.com/asa918.bin",
        asdmImageUrl="https://example.com/asdm718.bin",
    )
    single_result = AsaGroupCompatibleVersions(
        per_device={"uid-1": [v1]},
        common_versions=[v1],
    )

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=1, items=[single_device])

    def fake_get_compatible_versions(
        self: AsaUpgradeVersionService, *, device_uids: list[str]
    ) -> AsaGroupCompatibleVersions:
        return single_result

    def stub_upgrade_init(self: AsaUpgradeVersionService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(
        AsaUpgradeVersionService, "get_compatible_versions", fake_get_compatible_versions
    )
    monkeypatch.setattr(AsaUpgradeVersionService, "__init__", stub_upgrade_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "upgrade",
            "compatible-versions",
            "-u",
            "uid-1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    payload = json.loads(result.output)
    assert payload["device_name"] == "branch-asa-01"
    assert len(payload["compatible_versions"]) == 1
    assert payload["compatible_versions"][0]["software_version"] == "9.18.4"
    assert "common_versions" not in payload
    assert "per_device" not in payload


def test_should_display_group_table_for_multi_device(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """Multi-device table should show common versions with Compatible Devices column."""
    group_versions = _sample_group_versions()

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_get_compatible_versions(
        self: AsaUpgradeVersionService, *, device_uids: list[str]
    ) -> AsaGroupCompatibleVersions:
        return group_versions

    def stub_upgrade_init(self: AsaUpgradeVersionService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(
        AsaUpgradeVersionService, "get_compatible_versions", fake_get_compatible_versions
    )
    monkeypatch.setattr(AsaUpgradeVersionService, "__init__", stub_upgrade_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "upgrade",
            "compatible-versions",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
        ],
    )

    assert result.exit_code == 0
    output = str(result.output)
    assert "9.18.4" in output
    assert "7.18(1.152)" in output
    assert "Common compatible versions" in output


def test_should_display_simple_table_for_single_device(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Single-device table should show device name header, no Compatible Devices column."""
    single_device = Device(uid="uid-1", name="branch-asa-01", deviceType="ASA")
    v1 = AsaCompatibleVersion(
        softwareVersion="9.18.4",
        asdmVersion="7.18(1.152)",
    )
    single_result = AsaGroupCompatibleVersions(
        per_device={"uid-1": [v1]},
        common_versions=[v1],
    )

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=1, items=[single_device])

    def fake_get_compatible_versions(
        self: AsaUpgradeVersionService, *, device_uids: list[str]
    ) -> AsaGroupCompatibleVersions:
        return single_result

    def stub_upgrade_init(self: AsaUpgradeVersionService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(
        AsaUpgradeVersionService, "get_compatible_versions", fake_get_compatible_versions
    )
    monkeypatch.setattr(AsaUpgradeVersionService, "__init__", stub_upgrade_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "upgrade",
            "compatible-versions",
            "-u",
            "uid-1",
        ],
    )

    assert result.exit_code == 0
    output = str(result.output)
    assert "branch-asa-01" in output
    assert "9.18.4" in output
    assert "Compatible Devices" not in output
    assert "Common compatible versions" not in output


def test_should_filter_devices_by_query(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """compatible-versions should pass query filter to inventory service with ASA device type."""
    captured_params: dict[str, Any] = {}
    query = "name:branch-*"

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured_params["query"] = query
        captured_params["limit"] = limit
        captured_params["offset"] = offset
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_get_compatible_versions(
        self: AsaUpgradeVersionService, *, device_uids: list[str]
    ) -> AsaGroupCompatibleVersions:
        return AsaGroupCompatibleVersions()

    def stub_upgrade_init(self: AsaUpgradeVersionService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(
        AsaUpgradeVersionService, "get_compatible_versions", fake_get_compatible_versions
    )
    monkeypatch.setattr(AsaUpgradeVersionService, "__init__", stub_upgrade_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "upgrade",
            "compatible-versions",
            "--query",
            query,
            "--limit",
            "10",
            "--offset",
            "5",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured_params["query"] == f"{query} AND deviceType:ASA"
    assert captured_params["limit"] == 10
    assert captured_params["offset"] == 5


def test_should_fail_without_device_filter(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    """compatible-versions should fail when no device filter is provided."""
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "upgrade",
            "compatible-versions",
        ],
    )

    assert result.exit_code != 0
    assert "Provide one of" in result.output


def test_should_fail_with_multiple_device_filters(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    """compatible-versions should fail when multiple device filters are provided."""
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "upgrade",
            "compatible-versions",
            "--query",
            "name:foo",
            "-u",
            "uid-1",
        ],
    )

    assert result.exit_code != 0
    assert "Provide only one of" in result.output


def test_should_show_no_versions_message_for_single_device(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Single device with no versions should show 'No compatible versions found'."""
    single_device = Device(uid="uid-1", name="branch-asa-01", deviceType="ASA")

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=1, items=[single_device])

    def fake_get_compatible_versions(
        self: AsaUpgradeVersionService, *, device_uids: list[str]
    ) -> AsaGroupCompatibleVersions:
        return AsaGroupCompatibleVersions(per_device={"uid-1": []})

    def stub_upgrade_init(self: AsaUpgradeVersionService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(
        AsaUpgradeVersionService, "get_compatible_versions", fake_get_compatible_versions
    )
    monkeypatch.setattr(AsaUpgradeVersionService, "__init__", stub_upgrade_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "upgrade",
            "compatible-versions",
            "-u",
            "uid-1",
        ],
    )

    assert result.exit_code == 0
    assert "No compatible versions found" in result.output


def test_should_show_no_common_versions_for_multi_device(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """Multi-device with empty intersection should show 'No common compatible versions found'."""

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_get_compatible_versions(
        self: AsaUpgradeVersionService, *, device_uids: list[str]
    ) -> AsaGroupCompatibleVersions:
        return AsaGroupCompatibleVersions()

    def stub_upgrade_init(self: AsaUpgradeVersionService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(
        AsaUpgradeVersionService, "get_compatible_versions", fake_get_compatible_versions
    )
    monkeypatch.setattr(AsaUpgradeVersionService, "__init__", stub_upgrade_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "upgrade",
            "compatible-versions",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
        ],
    )

    assert result.exit_code == 0
    assert "No common compatible versions found" in result.output
