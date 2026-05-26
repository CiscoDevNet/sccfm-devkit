# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for sccfm_cli inventory devices asa ha-check command."""

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import CdoTransaction, Device, DevicePage

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.models.asa_failover_status import (
    AsaFailoverInterface,
    AsaFailoverStatus,
    AsaFailoverUnit,
    HaCheckResult,
)
from sccfm_core.services import AsaHaCheckReport, AsaHaCheckService, InventoryService
from sccfm_core.services.inventory.asa_ha_check_service import UnmonitoredInterface

# ── Sample data ──────────────────────────────────────────────────

_HEALTHY_STATUS = AsaFailoverStatus(
    failover_enabled=True,
    failover_unit="Primary",
    lan_interface_name="INTFC",
    lan_hardware="GigabitEthernet0/8",
    lan_state="up",
    version_ours="9.20(3)10",
    version_mate="9.20(3)10",
    serial_ours="JAD251400QT",
    serial_mate="9AA77409PDA",
    last_failover="14:23:15 UTC Jun 5 2024",
    monitored_count=3,
    monitored_max=110,
    this_host=AsaFailoverUnit(
        role="Primary",
        state="Active",
        active_time=12345,
        interfaces=[
            AsaFailoverInterface(
                name="outside", ip_address="10.0.0.1", status="Normal", monitoring="Monitored"
            ),
            AsaFailoverInterface(
                name="inside", ip_address="192.168.1.1", status="Normal", monitoring="Monitored"
            ),
        ],
    ),
    other_host=AsaFailoverUnit(
        role="Secondary",
        state="Standby Ready",
        active_time=0,
        interfaces=[
            AsaFailoverInterface(
                name="outside", ip_address="10.0.0.2", status="Normal", monitoring="Monitored"
            ),
            AsaFailoverInterface(
                name="inside", ip_address="192.168.1.2", status="Normal", monitoring="Monitored"
            ),
        ],
    ),
    config_sync_state="Sync Done",
)


def _sample_reports() -> dict[str, AsaHaCheckReport]:
    return {
        "uid-1": AsaHaCheckReport(
            failover_status=_HEALTHY_STATUS,
            checks=[
                HaCheckResult(name="failover_enabled", passed=True, detail="Failover is ON"),
                HaCheckResult(
                    name="lan_link",
                    passed=True,
                    detail="LAN failover link GigabitEthernet0/8 is up",
                ),
                HaCheckResult(
                    name="version_match", passed=True, detail="Both units running 9.20(3)10"
                ),
                HaCheckResult(name="mate_ready", passed=True, detail="Mate is Standby Ready"),
                HaCheckResult(
                    name="interfaces_healthy",
                    passed=True,
                    detail="All 3 monitored interfaces Normal",
                ),
                HaCheckResult(
                    name="config_synced", passed=True, detail="Configuration sync completed"
                ),
                HaCheckResult(
                    name="unmonitored_interfaces",
                    passed=True,
                    detail="All enabled named interfaces are monitored for failover",
                ),
            ],
            unmonitored_interfaces=[],
        ),
    }


def _sample_reports_with_failures() -> dict[str, AsaHaCheckReport]:
    return {
        "uid-1": AsaHaCheckReport(
            failover_status=_HEALTHY_STATUS,
            checks=[
                HaCheckResult(name="failover_enabled", passed=True, detail="Failover is ON"),
                HaCheckResult(name="lan_link", passed=True, detail="LAN failover link is up"),
                HaCheckResult(
                    name="version_match",
                    passed=False,
                    detail="Version mismatch: ours=9.20(3)10, mate=9.18(4)5",
                ),
                HaCheckResult(name="mate_ready", passed=True, detail="Mate is Standby Ready"),
                HaCheckResult(
                    name="interfaces_healthy",
                    passed=True,
                    detail="All 3 monitored interfaces Normal",
                ),
                HaCheckResult(
                    name="config_synced", passed=True, detail="Configuration sync completed"
                ),
                HaCheckResult(
                    name="unmonitored_interfaces",
                    passed=False,
                    detail="Enabled interfaces not monitored: dmz (GigabitEthernet0/3)",
                ),
            ],
            unmonitored_interfaces=[
                UnmonitoredInterface(hardware_name="GigabitEthernet0/3", name="dmz"),
            ],
        ),
    }


# ── Helpers ──────────────────────────────────────────────────────


def _patch_services(
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    reports: dict[str, AsaHaCheckReport],
    captured: dict[str, Any] | None = None,
) -> None:
    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        if captured is not None:
            captured["query"] = query
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_check_ha(
        self: AsaHaCheckService, device_uids: list[str]
    ) -> dict[str, AsaHaCheckReport]:
        if captured is not None:
            captured["device_uids"] = device_uids
        return reports

    def stub_init(self: AsaHaCheckService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaHaCheckService, "check_ha", fake_check_ha)
    monkeypatch.setattr(AsaHaCheckService, "__init__", stub_init)


# ── JSON output tests ────────────────────────────────────────────


def test_should_return_ha_check_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    captured: dict[str, Any] = {}
    _patch_services(monkeypatch, sample_devices, _sample_reports(), captured)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "ha-check", "-u", "uid-1", "--format", "json"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    payload = json.loads(result.output)
    assert len(payload) == 1

    report = payload[0]
    assert report["device_uid"] == "uid-1"
    assert report["all_passed"] is True
    assert len(report["checks"]) == 7
    assert report["failover_unit"] == "Primary"
    assert report["this_host_state"] == "Active"
    assert report["other_host_state"] == "Standby Ready"


def test_should_return_failures_in_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    _patch_services(monkeypatch, sample_devices, _sample_reports_with_failures())

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "ha-check", "-u", "uid-1", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    report = payload[0]
    assert report["all_passed"] is False
    failed_checks = [c for c in report["checks"] if not c["passed"]]
    assert len(failed_checks) == 2
    assert report["unmonitored_interfaces"][0]["name"] == "dmz"


def test_should_render_failed_transaction_as_json_when_requested(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def fake_check_ha(self: AsaHaCheckService, device_uids: list[str]) -> CdoTransaction:
        return CdoTransaction(
            transactionUid="tx-123",
            cdoTransactionStatus="ERROR",
            errorMessage="HA check execution failed",
        )

    def stub_init(self: AsaHaCheckService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaHaCheckService, "check_ha", fake_check_ha)
    monkeypatch.setattr(AsaHaCheckService, "__init__", stub_init)

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "ha-check", "-u", "uid-1", "--format", "json"],
    )

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["transactionUid"] == "tx-123"
    assert payload["cdoTransactionStatus"] == "ERROR"


# ── Table output tests ──────────────────────────────────────────


def test_should_display_ha_check_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    _patch_services(monkeypatch, sample_devices, _sample_reports())

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "ha-check", "-u", "uid-1"],
    )

    assert result.exit_code == 0
    output = result.output
    assert "perimeter-fw" in output
    assert "PASS" in output
    assert "failover_enabled" in output


def test_should_display_failures_in_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
) -> None:
    _patch_services(monkeypatch, sample_devices, _sample_reports_with_failures())

    result = cli_runner.invoke(
        cli,
        ["inventory", "devices", "asa", "ha-check", "-u", "uid-1"],
    )

    assert result.exit_code == 0
    output = result.output
    assert "FAIL" in output
    assert "dmz" in output
