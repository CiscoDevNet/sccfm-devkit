# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import CdoTransaction, Device, DevicePage

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.models.asa_disk_file import AsaDiskFile, AsaDiskFileType
from sccfm_core.services import AsaDiskFileService, InventoryService


def _sample_disk_files() -> dict[str, list[AsaDiskFile]]:
    return {
        "uid-1": [
            AsaDiskFile(
                name="asa917-51-k8.bin",
                size=21199744,
                date="Dec 14 2023 15:30:22",
                file_type=AsaDiskFileType.OS_IMAGE,
            ),
            AsaDiskFile(
                name="anyconnect-win-4.10.pkg",
                size=12345678,
                date="Jan 05 2024 10:20:30",
                file_type=AsaDiskFileType.ANYCONNECT_PACKAGE,
            ),
        ],
        "uid-2": [
            AsaDiskFile(
                name="asdm-7181.bin",
                size=56789012,
                date="Feb 10 2024 11:15:00",
                file_type=AsaDiskFileType.ASDM_IMAGE,
            ),
        ],
    }


def test_should_return_disk_files_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """disk list-files should return valid JSON when format is json."""
    captured_params: dict[str, Any] = {}
    disk_files = _sample_disk_files()

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_list_disk_files(
        self: AsaDiskFileService, *, device_uids: list[str]
    ) -> dict[str, list[AsaDiskFile]]:
        captured_params["device_uids"] = device_uids
        return disk_files

    def stub_disk_file_init(self: AsaDiskFileService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaDiskFileService, "list_disk_files", fake_list_disk_files)
    monkeypatch.setattr(AsaDiskFileService, "__init__", stub_disk_file_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "disk",
            "list-files",
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
    assert len(payload) == 3  # 2 files for uid-1, 1 file for uid-2
    assert payload[0]["file_name"] == "asa917-51-k8.bin"
    assert payload[0]["file_type"] == "OS_IMAGE"
    assert payload[0]["device_name"] == "perimeter-fw"
    assert payload[1]["file_type"] == "ANYCONNECT_PACKAGE"
    assert payload[2]["file_type"] == "ASDM_IMAGE"


def test_should_display_disk_files_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """disk list-files should display a formatted table by default."""
    disk_files = _sample_disk_files()

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_list_disk_files(
        self: AsaDiskFileService, *, device_uids: list[str]
    ) -> dict[str, list[AsaDiskFile]]:
        return disk_files

    def stub_disk_file_init(self: AsaDiskFileService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaDiskFileService, "list_disk_files", fake_list_disk_files)
    monkeypatch.setattr(AsaDiskFileService, "__init__", stub_disk_file_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "disk",
            "list-files",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
        ],
    )

    assert result.exit_code == 0
    output = str(result.output)
    # Rich may truncate long values in narrow terminals, so check for key substrings
    assert "uid-1" in output
    assert "uid-2" in output
    assert "OS_IMAGE" in output
    assert "ASDM_IMAGE" in output
    assert "Device Name" in output
    assert "File Name" in output
    assert "Type" in output


def test_should_filter_devices_by_query(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """disk list-files should pass query filter to inventory service with ASA device type."""
    captured_params: dict[str, Any] = {}
    query = "name:branch-*"

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        captured_params["query"] = query
        captured_params["limit"] = limit
        captured_params["offset"] = offset
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_list_disk_files(
        self: AsaDiskFileService, *, device_uids: list[str]
    ) -> dict[str, list[AsaDiskFile]]:
        return {}

    def stub_disk_file_init(self: AsaDiskFileService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaDiskFileService, "list_disk_files", fake_list_disk_files)
    monkeypatch.setattr(AsaDiskFileService, "__init__", stub_disk_file_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "disk",
            "list-files",
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
    """disk list-files should fail when no device filter is provided."""
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "disk",
            "list-files",
        ],
    )

    assert result.exit_code != 0
    assert "Provide one of" in result.output


def test_should_fail_with_multiple_device_filters(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    """disk list-files should fail when multiple device filters are provided."""
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "disk",
            "list-files",
            "--query",
            "name:foo",
            "-u",
            "uid-1",
        ],
    )

    assert result.exit_code != 0
    assert "Provide only one of" in result.output
