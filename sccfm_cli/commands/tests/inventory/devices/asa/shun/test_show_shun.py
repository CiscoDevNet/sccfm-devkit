# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for sccfm_cli inventory devices asa shun show command."""

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import Device, DevicePage

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.models.asa_shun_entry import AsaShunEntry, AsaShunInterfaceStats
from sccfm_core.services import InventoryService
from sccfm_core.services.inventory.asa_shun_service import AsaShunService

# ── Sample data ──────────────────────────────────────────────────


def _sample_shun_entries() -> dict[str, list[AsaShunEntry]]:
    return {
        "uid-1": [
            AsaShunEntry(
                interface="outside",
                source_ip="10.1.1.27",
                destination_ip="10.2.2.89",
                source_port=555,
                destination_port=666,
                protocol=6,
            ),
        ],
        "uid-2": [
            AsaShunEntry(
                interface="inside",
                source_ip="192.168.1.100",
                destination_ip="0.0.0.0",
                source_port=0,
                destination_port=0,
                protocol=0,
            ),
            AsaShunEntry(
                interface="dmz",
                source_ip="172.16.0.50",
                destination_ip="10.0.0.1",
                source_port=12345,
                destination_port=443,
                protocol=6,
            ),
        ],
    }


def _sample_shun_statistics() -> dict[str, list[AsaShunInterfaceStats]]:
    return {
        "uid-1": [
            AsaShunInterfaceStats(interface="outside", shunned=3, received=150),
            AsaShunInterfaceStats(interface="inside", shunned=0, received=42),
        ],
        "uid-2": [
            AsaShunInterfaceStats(interface="outside", shunned=1, received=88),
        ],
    }


# ── Helpers ──────────────────────────────────────────────────────


def _patch_services(
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    shun_entries: dict[str, list[AsaShunEntry]] | None = None,
    shun_statistics: dict[str, list[AsaShunInterfaceStats]] | None = None,
    captured: dict[str, Any] | None = None,
) -> None:
    """Wire up monkeypatches for InventoryService + AsaShunService."""

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        if captured is not None:
            captured["query"] = query
            captured["limit"] = limit
            captured["offset"] = offset
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_view_shun(
        self: AsaShunService, device_uids: list[str]
    ) -> dict[str, list[AsaShunEntry]]:
        if captured is not None:
            captured["device_uids"] = device_uids
        return shun_entries or {}

    def fake_view_shun_statistics(
        self: AsaShunService, device_uids: list[str]
    ) -> dict[str, list[AsaShunInterfaceStats]]:
        if captured is not None:
            captured["device_uids"] = device_uids
        return shun_statistics or {}

    def stub_init(self: AsaShunService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaShunService, "view_shun", fake_view_shun)
    monkeypatch.setattr(AsaShunService, "view_shun_statistics", fake_view_shun_statistics)
    monkeypatch.setattr(AsaShunService, "__init__", stub_init)


# ── JSON output: shun entries ────────────────────────────────────


def test_should_return_shun_entries_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """shun show returns valid JSON with expected shun entry fields."""
    captured: dict[str, Any] = {}
    _patch_services(
        monkeypatch, sample_devices, shun_entries=_sample_shun_entries(), captured=captured
    )

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "show",
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
    assert first["device_uid"] == "uid-1"
    assert first["device_name"] == "perimeter-fw"
    assert len(first["shun_entries"]) == 1
    assert first["shun_entries"][0]["source_ip"] == "10.1.1.27"
    assert first["shun_entries"][0]["protocol"] == 6

    second = payload[1]
    assert second["device_uid"] == "uid-2"
    assert len(second["shun_entries"]) == 2


# ── Table output: shun entries ───────────────────────────────────


def test_should_display_shun_entries_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """shun show renders a table with expected columns."""
    _patch_services(monkeypatch, sample_devices, shun_entries=_sample_shun_entries())

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "shun", "show", "-u", "uid-1", "-u", "uid-2"],
    )

    assert result.exit_code == 0
    output = result.output
    # Rich may truncate cell values in narrow terminals; check partial prefixes
    assert "10.1.1" in output
    assert "192.16" in output
    assert "172.16" in output


# ── JSON output: statistics ──────────────────────────────────────


def test_should_return_statistics_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """shun show --statistics returns valid JSON with per-interface counters."""
    captured: dict[str, Any] = {}
    _patch_services(
        monkeypatch, sample_devices, shun_statistics=_sample_shun_statistics(), captured=captured
    )

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "show",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--statistics",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"

    payload = json.loads(result.output)
    assert len(payload) == 2

    first = payload[0]
    assert first["device_uid"] == "uid-1"
    assert len(first["interface_stats"]) == 2
    assert first["interface_stats"][0]["interface"] == "outside"
    assert first["interface_stats"][0]["shunned"] == 3
    assert first["interface_stats"][0]["received"] == 150


# ── Table output: statistics ─────────────────────────────────────


def test_should_display_statistics_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """shun show --statistics renders a table with shunned/received counters."""
    _patch_services(monkeypatch, sample_devices, shun_statistics=_sample_shun_statistics())

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "show",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--statistics",
        ],
    )

    assert result.exit_code == 0
    output = result.output
    assert "outside" in output
    assert "150" in output


# ── Device name filter ───────────────────────────────────────────


def test_should_accept_device_names(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """shun show accepts -n flags to filter by device name."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, shun_entries={}, captured=captured)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "shun", "show", "-n", "branch-*", "--format", "json"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "name:branch-*" in captured["query"]
    assert "deviceType:ASA" in captured["query"]


# ── Query filter ─────────────────────────────────────────────────


def test_should_filter_devices_by_query(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """shun show passes --query to inventory with ASA type appended."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, shun_entries={}, captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "show",
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
    """shun show fails when no device selector is provided."""
    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "shun", "show"],
    )

    assert result.exit_code != 0
    assert "Provide one of" in result.output
