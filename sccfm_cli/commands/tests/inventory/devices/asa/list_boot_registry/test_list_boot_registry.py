# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for sccfm_cli inventory devices asa list-boot-registry command."""

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import Device, DevicePage

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.models.asa_boot_registry import AsaBootRegistry
from sccfm_core.services import AsaBootRegistryService, InventoryService

# ── Sample data ──────────────────────────────────────────────────


def _sample_boot_registry() -> dict[str, AsaBootRegistry]:
    return {
        "uid-1": AsaBootRegistry(
            system_image_file="disk0:/asa9-16-4-42-smp-k8.bin",
            compiled_date="Fri 22-Sep-23 03:23 GMT",
            config_register="unknown",
            config_modified=False,
            boot_system_entries=[],
        ),
        "uid-2": AsaBootRegistry(
            system_image_file="disk0:/asa9182-lfbff-k8.SPA",
            compiled_date="Thu 08-Jun-23 15:20 UTC",
            config_register="0x41",
            config_modified=True,
            boot_system_entries=[
                "disk0:/asa9182-lfbff-k8.SPA",
                "disk0:/asa9181-lfbff-k8.SPA",
            ],
        ),
    }


# ── Helpers ──────────────────────────────────────────────────────


def _patch_services(
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    boot_registry: dict[str, AsaBootRegistry],
    captured: dict[str, Any] | None = None,
) -> None:
    """Wire up monkeypatches for InventoryService + AsaBootRegistryService."""

    def fake_get_devices(
        self: InventoryService,
        *,
        limit: int,
        offset: int,
        query: str | None = None,
    ) -> DevicePage:
        if captured is not None:
            captured["query"] = query
            captured["limit"] = limit
            captured["offset"] = offset
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_list_boot_registry(
        self: AsaBootRegistryService,
        device_uids: list[str],
    ) -> dict[str, AsaBootRegistry]:
        if captured is not None:
            captured["device_uids"] = device_uids
        return boot_registry

    def stub_boot_init(self: AsaBootRegistryService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaBootRegistryService, "list_boot_registry", fake_list_boot_registry)
    monkeypatch.setattr(AsaBootRegistryService, "__init__", stub_boot_init)


# ── JSON output ──────────────────────────────────────────────────


def test_should_return_boot_registry_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """list-boot-registry returns valid JSON with expected fields."""
    captured: dict[str, Any] = {}
    boot_registry = _sample_boot_registry()
    _patch_services(monkeypatch, sample_devices, boot_registry, captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-boot-registry",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured["device_uids"] == ["uid-1", "uid-2"]

    payload = json.loads(result.output)
    assert len(payload) == 2

    first = payload[0]
    assert first["device_name"] == "perimeter-fw"
    assert first["device_uid"] == "uid-1"
    assert first["system_image_file"] == "disk0:/asa9-16-4-42-smp-k8.bin"
    assert first["config_modified"] is False
    assert first["boot_system_entries"] == []

    second = payload[1]
    assert second["device_name"] == "edge-nva"
    assert second["config_register"] == "0x41"
    assert second["config_modified"] is True
    assert len(second["boot_system_entries"]) == 2


# ── Table output ─────────────────────────────────────────────────


def test_should_display_boot_registry_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """list-boot-registry renders a table with the expected columns."""
    _patch_services(monkeypatch, sample_devices, _sample_boot_registry())

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-boot-registry",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
        ],
    )

    assert result.exit_code == 0
    output = result.output
    # Rich may wrap column headers in narrow terminals, so check for
    # key substrings that will survive wrapping.
    assert "uid-1" in output
    assert "uid-2" in output
    assert "perimeter-fw" in output or "perimet" in output
    assert "edge-nva" in output
    assert "System" in output
    assert "Config" in output
    assert "No" in output  # config_modified == False for uid-1
    assert "Yes" in output  # config_modified == True for uid-2


# ── Device name filter ───────────────────────────────────────────


def test_should_accept_device_names(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """list-boot-registry accepts -n flags to filter by device name."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, _sample_boot_registry(), captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-boot-registry",
            "-n",
            "branch-*",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "name:branch-*" in captured["query"]
    assert "deviceType:ASA" in captured["query"]


# ── Combined names and UIDs ──────────────────────────────────────


def test_should_combine_names_and_uids(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """list-boot-registry allows -n and -u to be combined."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, _sample_boot_registry(), captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-boot-registry",
            "-n",
            "Dayton",
            "-u",
            "uid-1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "name:Dayton" in captured["query"]
    assert "uid:uid-1" in captured["query"]
    assert " OR " in captured["query"]
    assert "deviceType:ASA" in captured["query"]


# ── Query filter ─────────────────────────────────────────────────


def test_should_filter_devices_by_query(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """list-boot-registry passes --query to inventory with ASA type appended."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, _sample_boot_registry(), captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-boot-registry",
            "--query",
            "name:branch-*",
            "--limit",
            "10",
            "--offset",
            "5",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured["query"] == "name:branch-* AND deviceType:ASA"
    assert captured["limit"] == 10
    assert captured["offset"] == 5


# ── Validation errors ────────────────────────────────────────────


def test_should_fail_without_any_filter(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    """list-boot-registry fails when no device selector is provided."""
    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "list-boot-registry"],
    )

    assert result.exit_code != 0
    assert "Provide at least one of" in result.output


def test_should_fail_when_query_combined_with_name(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    """list-boot-registry fails when --query is combined with -n."""
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-boot-registry",
            "--query",
            "name:foo",
            "-n",
            "bar",
        ],
    )

    assert result.exit_code != 0
    assert "--query cannot be combined" in result.output


def test_should_fail_when_query_combined_with_uid(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    """list-boot-registry fails when --query is combined with -u."""
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "list-boot-registry",
            "--query",
            "name:foo",
            "-u",
            "uid-1",
        ],
    )

    assert result.exit_code != 0
    assert "--query cannot be combined" in result.output
