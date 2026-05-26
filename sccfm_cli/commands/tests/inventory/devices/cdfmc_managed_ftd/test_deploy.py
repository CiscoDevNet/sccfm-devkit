# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the ``sccfm_cli inventory devices cdfmc-managed-ftd deploy`` command."""

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import (
    CdoTransaction,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
)

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services import InventoryService
from sccfm_core.services.inventory.ftd_deploy_service import FtdDeployService
from sccfm_core.services.transaction_service import TransactionService


def _fake_transaction(uid: str = "txn-1") -> CdoTransaction:
    return CdoTransaction(
        transactionUid=uid,
        cdoTransactionStatus="PENDING",
    )


def _single_device() -> Device:
    return Device(
        uid="uid-1",
        name="branch-ftd-01",
        deviceType=EntityType.CDFMC_MANAGED_FTD,
        connectivityState=ConnectivityState.ONLINE,
    )


def _two_devices() -> list[Device]:
    return [
        Device(
            uid="uid-1",
            name="branch-ftd-01",
            deviceType=EntityType.CDFMC_MANAGED_FTD,
            connectivityState=ConnectivityState.ONLINE,
        ),
        Device(
            uid="uid-2",
            name="branch-ftd-02",
            deviceType=EntityType.CDFMC_MANAGED_FTD,
            connectivityState=ConnectivityState.ONLINE,
        ),
    ]


# ── Helpers ─────────────────────────────────────────────────────


def _stub_deploy_init(self: FtdDeployService, config: Any) -> None:
    return None


def _patch_inventory(monkeypatch: MonkeyPatch, devices: list[Device]) -> None:
    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(devices), items=devices)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)


# ── Single device tests ────────────────────────────────────────


class TestSingleDeviceDeploy:
    def test_should_deploy_single_device_json(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(FtdDeployService, "__init__", _stub_deploy_init)

        captured: dict[str, Any] = {}

        def fake_deploy_single(self: FtdDeployService, **kwargs: Any) -> CdoTransaction:
            captured.update(kwargs)
            return _fake_transaction("txn-single")

        monkeypatch.setattr(FtdDeployService, "deploy_single", fake_deploy_single)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "deploy",
                "-u",
                "uid-1",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output)
        assert payload["transactionUid"] == "txn-single"
        assert captured["device_uid"] == "uid-1"
        assert captured["ignore_warnings"] is False

    def test_should_deploy_with_optional_params(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(FtdDeployService, "__init__", _stub_deploy_init)

        captured: dict[str, Any] = {}

        def fake_deploy_single(self: FtdDeployService, **kwargs: Any) -> CdoTransaction:
            captured.update(kwargs)
            return _fake_transaction()

        monkeypatch.setattr(FtdDeployService, "deploy_single", fake_deploy_single)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "deploy",
                "-u",
                "uid-1",
                "--deployment-notes",
                "Ticket-123",
                "--description",
                "Policy update",
                "--ignore-warnings",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured["deployment_notes"] == "Ticket-123"
        assert captured["description"] == "Policy update"
        assert captured["ignore_warnings"] is True

    def test_should_deploy_table_format(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(FtdDeployService, "__init__", _stub_deploy_init)

        def fake_deploy_single(self: FtdDeployService, **kwargs: Any) -> CdoTransaction:
            return _fake_transaction("txn-table")

        monkeypatch.setattr(FtdDeployService, "deploy_single", fake_deploy_single)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "deploy",
                "-u",
                "uid-1",
                "--format",
                "table",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Deploy triggered" in result.output
        assert "txn-table" in result.output


# ── Multiple device tests ──────────────────────────────────────


class TestMultipleDeviceDeploy:
    def test_should_deploy_multiple_devices_json(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        devices = _two_devices()
        _patch_inventory(monkeypatch, devices)
        monkeypatch.setattr(FtdDeployService, "__init__", _stub_deploy_init)

        captured: dict[str, Any] = {}

        def fake_deploy_multiple(self: FtdDeployService, **kwargs: Any) -> CdoTransaction:
            captured.update(kwargs)
            return _fake_transaction("txn-multi")

        monkeypatch.setattr(FtdDeployService, "deploy_multiple", fake_deploy_multiple)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "deploy",
                "-u",
                "uid-1",
                "-u",
                "uid-2",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output)
        assert payload["transactionUid"] == "txn-multi"
        assert set(captured["device_uids"]) == {"uid-1", "uid-2"}

    def test_should_deploy_multiple_with_ignore_warnings(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        devices = _two_devices()
        _patch_inventory(monkeypatch, devices)
        monkeypatch.setattr(FtdDeployService, "__init__", _stub_deploy_init)

        captured: dict[str, Any] = {}

        def fake_deploy_multiple(self: FtdDeployService, **kwargs: Any) -> CdoTransaction:
            captured.update(kwargs)
            return _fake_transaction()

        monkeypatch.setattr(FtdDeployService, "deploy_multiple", fake_deploy_multiple)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "deploy",
                "-u",
                "uid-1",
                "-u",
                "uid-2",
                "--ignore-warnings",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured["ignore_warnings"] is True


# ── Check mode tests ──────────────────────────────────────────


class TestCheckMode:
    def test_should_report_check_targets_json(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "deploy",
                "-u",
                "uid-1",
                "--check",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output)
        assert payload["can_proceed"] is True
        assert payload["matched_devices"] == 1

    def test_should_report_check_targets_table(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "deploy",
                "-u",
                "uid-1",
                "--check",
                "--format",
                "table",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "1 device(s) matched" in result.output


# ── Wait mode tests ───────────────────────────────────────────


def _stub_transaction_init(self: TransactionService, config: Any) -> None:
    return None


class TestWaitMode:
    def test_should_wait_and_show_completed(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(FtdDeployService, "__init__", _stub_deploy_init)
        monkeypatch.setattr(TransactionService, "__init__", _stub_transaction_init)

        def fake_deploy_single(self: FtdDeployService, **kwargs: Any) -> CdoTransaction:
            return CdoTransaction(transactionUid="txn-wait", cdoTransactionStatus="PENDING")

        monkeypatch.setattr(FtdDeployService, "deploy_single", fake_deploy_single)

        done_txn = CdoTransaction(transactionUid="txn-wait", cdoTransactionStatus="DONE")

        def fake_wait(
            self: TransactionService,
            transaction_uid: str,
            timeout_sec: int = 3600,
            polling_interval_sec: int = 10,
            on_poll: Any = None,
        ) -> CdoTransaction:
            return done_txn

        monkeypatch.setattr(TransactionService, "wait_for_transaction_to_finish", fake_wait)

        result = cli_runner.invoke(
            cli,
            [
                "--silent",
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "deploy",
                "-u",
                "uid-1",
                "--wait",
                "--format",
                "table",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Deploy completed" in result.output
        assert "DONE" in result.output

    def test_should_wait_and_show_failed(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(FtdDeployService, "__init__", _stub_deploy_init)
        monkeypatch.setattr(TransactionService, "__init__", _stub_transaction_init)

        def fake_deploy_single(self: FtdDeployService, **kwargs: Any) -> CdoTransaction:
            return CdoTransaction(transactionUid="txn-fail", cdoTransactionStatus="PENDING")

        monkeypatch.setattr(FtdDeployService, "deploy_single", fake_deploy_single)

        error_txn = CdoTransaction(
            transactionUid="txn-fail",
            cdoTransactionStatus="ERROR",
            errorMessage="Deployment validation failed",
        )

        def fake_wait(
            self: TransactionService,
            transaction_uid: str,
            timeout_sec: int = 3600,
            polling_interval_sec: int = 10,
            on_poll: Any = None,
        ) -> CdoTransaction:
            return error_txn

        monkeypatch.setattr(TransactionService, "wait_for_transaction_to_finish", fake_wait)

        result = cli_runner.invoke(
            cli,
            [
                "--silent",
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "deploy",
                "-u",
                "uid-1",
                "--wait",
                "--format",
                "table",
            ],
        )

        assert result.exit_code == 1
        assert "Deploy failed" in result.output
        assert "Deployment validation failed" in result.output

    def test_should_wait_json_output(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(FtdDeployService, "__init__", _stub_deploy_init)
        monkeypatch.setattr(TransactionService, "__init__", _stub_transaction_init)

        def fake_deploy_single(self: FtdDeployService, **kwargs: Any) -> CdoTransaction:
            return CdoTransaction(transactionUid="txn-json", cdoTransactionStatus="PENDING")

        monkeypatch.setattr(FtdDeployService, "deploy_single", fake_deploy_single)

        done_txn = CdoTransaction(transactionUid="txn-json", cdoTransactionStatus="DONE")

        def fake_wait(
            self: TransactionService,
            transaction_uid: str,
            timeout_sec: int = 3600,
            polling_interval_sec: int = 10,
            on_poll: Any = None,
        ) -> CdoTransaction:
            return done_txn

        monkeypatch.setattr(TransactionService, "wait_for_transaction_to_finish", fake_wait)

        result = cli_runner.invoke(
            cli,
            [
                "--silent",
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "deploy",
                "-u",
                "uid-1",
                "--wait",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output)
        assert payload["transactionUid"] == "txn-json"
        assert payload["cdoTransactionStatus"] == "DONE"

    def test_no_wait_returns_pending(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Without --wait, the transaction should be returned as-is (PENDING)."""
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(FtdDeployService, "__init__", _stub_deploy_init)

        def fake_deploy_single(self: FtdDeployService, **kwargs: Any) -> CdoTransaction:
            return _fake_transaction("txn-nowait")

        monkeypatch.setattr(FtdDeployService, "deploy_single", fake_deploy_single)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "deploy",
                "-u",
                "uid-1",
                "--no-wait",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output)
        assert payload["transactionUid"] == "txn-nowait"
        assert payload["cdoTransactionStatus"] == "PENDING"


# ── Validation tests ───────────────────────────────────────────


class TestValidation:
    def test_should_fail_when_no_device_filter_provided(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
    ) -> None:
        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "deploy",
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0

    def test_should_deploy_with_device_name(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(FtdDeployService, "__init__", _stub_deploy_init)

        def fake_deploy_single(self: FtdDeployService, **kwargs: Any) -> CdoTransaction:
            return _fake_transaction()

        monkeypatch.setattr(FtdDeployService, "deploy_single", fake_deploy_single)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "deploy",
                "-n",
                "branch-ftd-01",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"

    def test_should_deploy_with_query(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(FtdDeployService, "__init__", _stub_deploy_init)

        def fake_deploy_single(self: FtdDeployService, **kwargs: Any) -> CdoTransaction:
            return _fake_transaction()

        monkeypatch.setattr(FtdDeployService, "deploy_single", fake_deploy_single)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "cdfmc-managed-ftd",
                "deploy",
                "-q",
                "name:branch-*",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
