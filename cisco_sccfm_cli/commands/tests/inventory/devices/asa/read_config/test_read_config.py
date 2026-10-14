# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the ``cisco_sccfm_cli inventory devices asa read-config`` command."""

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import CdoTransaction, Device, DevicePage, EntityType

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.models import Config
from cisco_sccfm_core.services import InventoryService
from cisco_sccfm_core.services.inventory import AsaConfigReadService
from cisco_sccfm_core.services.transaction_service import TransactionService

_READ_CONFIG = ["inventory", "devices", "asa", "read-config"]


def _transaction(status: str = "PENDING") -> CdoTransaction:
    return CdoTransaction(transactionUid="txn-1", cdoTransactionStatus=status)


def _devices(count: int) -> list[Device]:
    return [
        Device(uid=f"uid-{i}", name=f"branch-asa-0{i}", deviceType=EntityType.ASA)
        for i in range(1, count + 1)
    ]


def _patch_inventory(monkeypatch: MonkeyPatch, devices: list[Device]) -> None:
    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(devices), items=devices)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)


def _patch_read(monkeypatch: MonkeyPatch, captured: dict[str, Any]) -> None:
    def stub_init(self: AsaConfigReadService, config: Any) -> None:
        return None

    def fake_read(self: AsaConfigReadService, *, device_uids: list[str]) -> CdoTransaction:
        captured["device_uids"] = device_uids
        return _transaction()

    monkeypatch.setattr(AsaConfigReadService, "__init__", stub_init)
    monkeypatch.setattr(AsaConfigReadService, "read_configuration", fake_read)


def _patch_wait(monkeypatch: MonkeyPatch, final_status: str) -> None:
    def stub_init(self: TransactionService, config: Any) -> None:
        return None

    def fake_wait(self: TransactionService, **kwargs: Any) -> CdoTransaction:
        return _transaction(final_status)

    monkeypatch.setattr(TransactionService, "__init__", stub_init)
    monkeypatch.setattr(TransactionService, "wait_for_transaction_to_finish", fake_wait)


def test_should_read_all_matched_devices_and_return_transaction_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    _patch_inventory(monkeypatch, _devices(2))
    captured: dict[str, Any] = {}
    _patch_read(monkeypatch, captured)

    result = cli_runner.invoke(cli, [*_READ_CONFIG, "--query", "name:branch-*", "--format", "json"])

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert json.loads(result.output)["transactionUid"] == "txn-1"
    assert captured["device_uids"] == ["uid-1", "uid-2"]


def test_should_wait_for_transaction_when_requested(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    _patch_inventory(monkeypatch, _devices(1))
    _patch_read(monkeypatch, {})
    _patch_wait(monkeypatch, "DONE")

    result = cli_runner.invoke(
        cli, ["--silent", *_READ_CONFIG, "-u", "uid-1", "--wait", "--format", "json"]
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert json.loads(result.output)["cdoTransactionStatus"] == "DONE"


def test_should_exit_non_zero_when_read_transaction_fails(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    _patch_inventory(monkeypatch, _devices(1))
    _patch_read(monkeypatch, {})
    _patch_wait(monkeypatch, "ERROR")

    result = cli_runner.invoke(
        cli, ["--silent", *_READ_CONFIG, "-u", "uid-1", "--wait", "--format", "json"]
    )

    assert result.exit_code != 0
    assert json.loads(result.output)["cdoTransactionStatus"] == "ERROR"


def test_should_fail_when_no_devices_match(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    _patch_inventory(monkeypatch, [])
    captured: dict[str, Any] = {}
    _patch_read(monkeypatch, captured)

    result = cli_runner.invoke(cli, [*_READ_CONFIG, "--query", "name:missing-*"])

    assert result.exit_code != 0
    assert "No ASA devices matched" in result.output
    assert captured == {}


def test_check_mode_should_report_targets_without_reading(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    _patch_inventory(monkeypatch, _devices(1))
    captured: dict[str, Any] = {}
    _patch_read(monkeypatch, captured)

    result = cli_runner.invoke(cli, [*_READ_CONFIG, "-u", "uid-1", "--check", "--format", "json"])

    assert result.exit_code == 0, f"Command failed: {result.output}"
    payload = json.loads(result.output)
    assert payload["operation"] == "configuration read"
    assert payload["matched_devices"] == 1
    assert captured == {}
