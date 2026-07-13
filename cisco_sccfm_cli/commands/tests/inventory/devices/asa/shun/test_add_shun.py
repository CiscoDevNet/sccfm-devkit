# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for cisco_sccfm_cli inventory devices asa shun add command."""

from __future__ import annotations

import json
from typing import Any, List

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import CdoCliResult, Device, DevicePage

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.models import Config
from cisco_sccfm_core.services import InventoryService
from cisco_sccfm_core.services.inventory.asa_shun_service import AsaShunService, ShunEntrySpec


def _sample_cli_results() -> list[CdoCliResult]:
    return [
        CdoCliResult(uid="cli-1", device_uid="uid-1", result="", error_msg=None),
        CdoCliResult(uid="cli-2", device_uid="uid-2", result="", error_msg=None),
    ]


def _patch_services(
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    cli_results: list[CdoCliResult] | None = None,
    captured: dict[str, Any] | None = None,
) -> None:
    """Wire up monkeypatches for InventoryService + AsaShunService."""

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        if captured is not None:
            captured["query"] = query
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_add_shun_entries(
        self: AsaShunService,
        device_uids: List[str],
        entries: List[ShunEntrySpec],
        *,
        wait: bool = True,
    ) -> list[CdoCliResult]:
        if captured is not None:
            captured["device_uids"] = device_uids
            captured["entries"] = entries
            captured["wait"] = wait
        return cli_results or _sample_cli_results()

    def stub_init(self: AsaShunService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaShunService, "add_shun_entries", fake_add_shun_entries)
    monkeypatch.setattr(AsaShunService, "__init__", stub_init)


def test_should_add_shun_single_source_ip(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """Single --source-ip sends one ShunEntrySpec to the service."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "--source-ip",
            "10.1.1.1",
            "-u",
            "uid-1",
            "--wait",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(captured["entries"]) == 1
    spec = captured["entries"][0]
    assert spec.source_ip == "10.1.1.1"
    assert spec.dest_ip is None


def test_should_add_shun_with_connection_tuple_flags(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """source-ip + --dest-ip/--source-port/--dest-port/--protocol flags work."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "--source-ip",
            "10.1.1.1",
            "--dest-ip",
            "10.2.2.2",
            "--source-port",
            "555",
            "--dest-port",
            "443",
            "--protocol",
            "tcp",
            "-u",
            "uid-1",
            "--wait",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    spec = captured["entries"][0]
    assert spec.source_ip == "10.1.1.1"
    assert spec.dest_ip == "10.2.2.2"
    assert spec.source_port == 555
    assert spec.dest_port == 443
    assert spec.protocol == "tcp"


def test_should_add_shun_with_inline_tuple(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """Inline connection tuple in --source-ip is parsed correctly."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "--source-ip",
            "10.1.1.1 10.2.2.2 555 443 tcp",
            "-u",
            "uid-1",
            "--wait",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    spec = captured["entries"][0]
    assert spec.source_ip == "10.1.1.1"
    assert spec.dest_ip == "10.2.2.2"
    assert spec.source_port == 555
    assert spec.dest_port == 443
    assert spec.protocol == "tcp"


def test_should_add_multiple_shun_entries(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """Multiple --source-ip flags send all entries in one call."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "--source-ip",
            "10.1.1.1",
            "--source-ip",
            "20.2.2.2 10.3.3.3 555 443 tcp",
            "--source-ip",
            "30.3.3.3",
            "-u",
            "uid-1",
            "--wait",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    entries = captured["entries"]
    assert len(entries) == 3

    assert entries[0].source_ip == "10.1.1.1"
    assert entries[0].dest_ip is None

    assert entries[1].source_ip == "20.2.2.2"
    assert entries[1].dest_ip == "10.3.3.3"
    assert entries[1].source_port == 555
    assert entries[1].dest_port == 443
    assert entries[1].protocol == "tcp"

    assert entries[2].source_ip == "30.3.3.3"


def test_should_reject_separate_flags_with_multiple_source_ips(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """--dest-ip cannot be combined with multiple --source-ip values."""
    _patch_services(monkeypatch, sample_devices)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "--source-ip",
            "10.1.1.1",
            "--source-ip",
            "10.2.2.2",
            "--dest-ip",
            "10.3.3.3",
            "-u",
            "uid-1",
            "--wait",
        ],
    )

    assert result.exit_code != 0
    assert "cannot be combined" in result.output


def test_should_reject_separate_flags_with_inline_tuple(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """--dest-ip cannot be combined with an inline connection tuple."""
    _patch_services(monkeypatch, sample_devices)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "--source-ip",
            "10.1.1.1 10.2.2.2 555 443 tcp",
            "--dest-ip",
            "10.3.3.3",
            "-u",
            "uid-1",
            "--wait",
        ],
    )

    assert result.exit_code != 0
    assert "cannot be combined" in result.output


def test_should_reject_missing_dest_ip_with_port_flags(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """--source-port without --dest-ip is rejected."""
    _patch_services(monkeypatch, sample_devices)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "--source-ip",
            "10.1.1.1",
            "--dest-port",
            "443",
            "-u",
            "uid-1",
            "--wait",
        ],
    )

    assert result.exit_code != 0
    assert "--dest-ip is required" in result.output


def test_should_reject_invalid_inline_port(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """Non-numeric port in inline tuple is rejected."""
    _patch_services(monkeypatch, sample_devices)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "--source-ip",
            "10.1.1.1 10.2.2.2 notaport 443 tcp",
            "-u",
            "uid-1",
            "--wait",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid source_port" in result.output


def test_should_reject_invalid_inline_protocol(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """Only tcp/udp is accepted in inline protocol field."""
    _patch_services(monkeypatch, sample_devices)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "add",
            "--source-ip",
            "10.1.1.1 10.2.2.2 555 443 icmp",
            "-u",
            "uid-1",
            "--wait",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid protocol" in result.output
