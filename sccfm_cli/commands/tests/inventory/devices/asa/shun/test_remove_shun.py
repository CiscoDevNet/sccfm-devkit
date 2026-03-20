"""Tests for sccfm_cli inventory devices asa shun remove command."""

from __future__ import annotations

import json
from typing import Any, List

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import CdoCliResult, Device, DevicePage

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services import InventoryService
from sccfm_core.services.inventory.asa_shun_service import AsaShunService


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

    def fake_remove_shun_entries(
        self: AsaShunService,
        device_uids: List[str],
        source_ips: List[str],
        *,
        wait: bool = True,
    ) -> list[CdoCliResult]:
        if captured is not None:
            captured["device_uids"] = device_uids
            captured["source_ips"] = source_ips
            captured["wait"] = wait
        return cli_results or _sample_cli_results()

    def stub_init(self: AsaShunService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaShunService, "remove_shun_entries", fake_remove_shun_entries)
    monkeypatch.setattr(AsaShunService, "__init__", stub_init)


def test_should_remove_single_source_ip(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """Single --source-ip sends one IP to the service."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "remove",
            "--source-ip",
            "10.1.1.1",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--wait",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["source_ips"] == ["10.1.1.1"]
    assert captured["device_uids"] == ["uid-1", "uid-2"]


def test_should_remove_multiple_source_ips_in_one_call(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """Repeating --source-ip sends all IPs in a single call."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "remove",
            "--source-ip",
            "10.1.1.1",
            "--source-ip",
            "10.2.2.2",
            "--source-ip",
            "10.3.3.3",
            "-u",
            "uid-1",
            "--wait",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["source_ips"] == ["10.1.1.1", "10.2.2.2", "10.3.3.3"]


def test_should_pass_wait_flag_to_service(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    """--wait flag is forwarded to the service."""
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "shun",
            "remove",
            "--source-ip",
            "10.1.1.1",
            "--wait",
            "-u",
            "uid-1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["wait"] is True
