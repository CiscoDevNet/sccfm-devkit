"""Tests for the ``sccfm_cli inventory devices asa upgrade trigger`` command."""

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import CdoTransaction, Device, DevicePage

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.services import InventoryService
from sccfm_core.services.inventory import AsaUpgradeService


def _fake_transaction(uid: str = "txn-1") -> CdoTransaction:
    return CdoTransaction(
        transactionUid=uid,
        cdoTransactionStatus="PENDING",
    )


def _single_device() -> Device:
    return Device(uid="uid-1", name="branch-asa-01", deviceType="ASA")


def _two_devices() -> list[Device]:
    return [
        Device(uid="uid-1", name="branch-asa-01", deviceType="ASA"),
        Device(uid="uid-2", name="branch-asa-02", deviceType="ASA"),
    ]


# ── Helpers ─────────────────────────────────────────────────────


def _stub_upgrade_init(self: AsaUpgradeService, config: Any) -> None:
    return None


def _patch_inventory(monkeypatch: MonkeyPatch, devices: list[Device]) -> None:
    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=len(devices), items=devices)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)


# ── Single device tests ────────────────────────────────────────


class TestSingleDeviceTrigger:
    def test_should_trigger_single_upgrade_json(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)

        captured: dict[str, Any] = {}

        def fake_upgrade_single(self: AsaUpgradeService, **kwargs: Any) -> CdoTransaction:
            captured.update(kwargs)
            return _fake_transaction("txn-single")

        monkeypatch.setattr(AsaUpgradeService, "upgrade_single", fake_upgrade_single)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "asa",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "--software-version",
                "9.18(4)",
                "--asdm-version",
                "7.18(1.152)",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output)
        assert payload["transactionUid"] == "txn-single"
        assert captured["device_uid"] == "uid-1"
        assert captured["software_version"] == "9.18(4)"
        assert captured["asdm_version"] == "7.18(1.152)"
        assert captured["stage_upgrade"] is False
        assert captured["force_upgrade"] is False

    def test_should_trigger_staged_upgrade(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)

        captured: dict[str, Any] = {}

        def fake_upgrade_single(self: AsaUpgradeService, **kwargs: Any) -> CdoTransaction:
            captured.update(kwargs)
            return _fake_transaction()

        monkeypatch.setattr(AsaUpgradeService, "upgrade_single", fake_upgrade_single)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "asa",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "--software-version",
                "9.18(4)",
                "--stage-upgrade",
                "--format",
                "table",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured["stage_upgrade"] is True
        assert "Staging triggered" in result.output

    def test_should_trigger_table_format(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)

        def fake_upgrade_single(self: AsaUpgradeService, **kwargs: Any) -> CdoTransaction:
            return _fake_transaction("txn-table")

        monkeypatch.setattr(AsaUpgradeService, "upgrade_single", fake_upgrade_single)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "asa",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "--software-version",
                "9.18(4)",
                "--format",
                "table",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Upgrade triggered" in result.output
        assert "txn-table" in result.output


# ── Multiple device tests ──────────────────────────────────────


class TestMultipleDeviceTrigger:
    def test_should_trigger_multi_upgrade_json(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        devices = _two_devices()
        _patch_inventory(monkeypatch, devices)
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)

        captured: dict[str, Any] = {}

        def fake_upgrade_multiple(self: AsaUpgradeService, **kwargs: Any) -> CdoTransaction:
            captured.update(kwargs)
            return _fake_transaction("txn-multi")

        monkeypatch.setattr(AsaUpgradeService, "upgrade_multiple", fake_upgrade_multiple)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "asa",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "-u",
                "uid-2",
                "--software-version",
                "9.18(4)",
                "--force-upgrade",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output)
        assert payload["transactionUid"] == "txn-multi"
        assert set(captured["device_uids"]) == {"uid-1", "uid-2"}
        assert captured["force_upgrade"] is True

    def test_should_trigger_multi_with_ignore_maintenance_window(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        devices = _two_devices()
        _patch_inventory(monkeypatch, devices)
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)

        captured: dict[str, Any] = {}

        def fake_upgrade_multiple(self: AsaUpgradeService, **kwargs: Any) -> CdoTransaction:
            captured.update(kwargs)
            return _fake_transaction()

        monkeypatch.setattr(AsaUpgradeService, "upgrade_multiple", fake_upgrade_multiple)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "asa",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "-u",
                "uid-2",
                "--software-version",
                "9.18(4)",
                "--ignore-maintenance-window",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured["ignore_maintenance_window"] is True


# ── Validation tests ───────────────────────────────────────────


class TestValidation:
    def test_should_fail_when_no_version_specified(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "asa",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        assert "software-version" in result.output or "asdm-version" in result.output

    def test_should_succeed_with_only_asdm_version(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)

        def fake_upgrade_single(self: AsaUpgradeService, **kwargs: Any) -> CdoTransaction:
            return _fake_transaction()

        monkeypatch.setattr(AsaUpgradeService, "upgrade_single", fake_upgrade_single)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "asa",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "--asdm-version",
                "7.18(1.152)",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"


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
                "asa",
                "upgrade",
                "trigger",
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
                "asa",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "--check",
                "--format",
                "table",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "1 device(s) matched" in result.output


# ── Upgrade name tests ────────────────────────────────────────


class TestUpgradeName:
    def test_should_pass_upgrade_name(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)

        captured: dict[str, Any] = {}

        def fake_upgrade_single(self: AsaUpgradeService, **kwargs: Any) -> CdoTransaction:
            captured.update(kwargs)
            return _fake_transaction()

        monkeypatch.setattr(AsaUpgradeService, "upgrade_single", fake_upgrade_single)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "asa",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "--software-version",
                "9.18(4)",
                "--upgrade-name",
                "Production ASA Upgrade - January 2025",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured["name"] == "Production ASA Upgrade - January 2025"
