# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the ``sccfm_cli inventory devices asa upgrade trigger`` command."""

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import (
    AsaCompatibleVersion,
    CdoTransaction,
    Device,
    DevicePage,
    EntityType,
)

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.models.asa_upgrade_version import AsaGroupCompatibleVersions
from sccfm_core.services import InventoryService
from sccfm_core.services.inventory import AsaUpgradeService, AsaUpgradeVersionService
from sccfm_core.services.transaction_service import TransactionService


def _fake_transaction(uid: str = "txn-1") -> CdoTransaction:
    return CdoTransaction(
        transactionUid=uid,
        cdoTransactionStatus="PENDING",
    )


def _single_device(asdm_version: str | None = None, software_version: str | None = None) -> Device:
    return Device(
        uid="uid-1",
        name="branch-asa-01",
        deviceType=EntityType.ASA,
        asdmVersion=asdm_version,
        softwareVersion=software_version,
    )


def _two_devices(
    asdm_version: str | None = None, software_version: str | None = None
) -> list[Device]:
    return [
        Device(
            uid="uid-1",
            name="branch-asa-01",
            deviceType=EntityType.ASA,
            asdmVersion=asdm_version,
            softwareVersion=software_version,
        ),
        Device(
            uid="uid-2",
            name="branch-asa-02",
            deviceType=EntityType.ASA,
            asdmVersion=asdm_version,
            softwareVersion=software_version,
        ),
    ]


def _cv(sw: str, asdm: str) -> AsaCompatibleVersion:
    return AsaCompatibleVersion(softwareVersion=sw, asdmVersion=asdm)


# ── Helpers ─────────────────────────────────────────────────────


def _stub_upgrade_init(self: AsaUpgradeService, config: Any) -> None:
    return None


def _stub_version_init(self: AsaUpgradeVersionService, config: Any) -> None:
    return None


def _patch_compatible_versions(
    monkeypatch: MonkeyPatch,
    common_versions: list[AsaCompatibleVersion],
) -> None:
    monkeypatch.setattr(AsaUpgradeVersionService, "__init__", _stub_version_init)

    def fake_get(
        self: AsaUpgradeVersionService, device_uids: list[str]
    ) -> AsaGroupCompatibleVersions:
        per_device = {uid: list(common_versions) for uid in device_uids}
        return AsaGroupCompatibleVersions(per_device=per_device, common_versions=common_versions)

    monkeypatch.setattr(AsaUpgradeVersionService, "get_compatible_versions", fake_get)


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
        device = _single_device(asdm_version="7.18(1.152)")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_cv("9.18(4)", "7.18(1.152)")])

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
        device = _single_device(asdm_version="7.18(1.152)")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_cv("9.18(4)", "7.18(1.152)")])

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
        device = _single_device(asdm_version="7.18(1.152)")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_cv("9.18(4)", "7.18(1.152)")])

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
        devices = _two_devices(asdm_version="7.18(1.152)")
        _patch_inventory(monkeypatch, devices)
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_cv("9.18(4)", "7.18(1.152)")])

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
        devices = _two_devices(asdm_version="7.18(1.152)")
        _patch_inventory(monkeypatch, devices)
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_cv("9.18(4)", "7.18(1.152)")])

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
        device = _single_device(asdm_version="7.5(2)", software_version="9.4(2)")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_cv("9.4(2)", "7.18(1.152)")])

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
        device = _single_device(asdm_version="7.18(1.152)")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_cv("9.18(4)", "7.18(1.152)")])

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


# ── ASDM compatibility validation tests ────────────────────────


class TestAsdmCompatibilityValidation:
    """Tests for ASDM compatibility checks when --software-version is given."""

    def test_should_fail_when_software_version_not_compatible(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device(asdm_version="7.5(2)")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_cv("9.4(2)", "7.5(2)")])

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
                "9.4(3)",
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        assert "not compatible" in result.output

    def test_should_fail_when_explicit_asdm_does_not_match_required(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device(asdm_version="7.5(2)")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_cv("9.4(3)", "7.6(1)")])

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
                "9.4(3)",
                "--asdm-version",
                "7.5(2)",
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        assert "7.5(2) is not compatible" in result.output
        assert "Minimum required ASDM version is 7.6(1)" in result.output

    def test_should_pass_when_explicit_asdm_is_in_compatible_set(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device(asdm_version="7.5(2)")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(
            monkeypatch,
            [_cv("9.4(3)", "7.6(1)"), _cv("9.4(3)", "7.7(1)")],
        )

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
                "--software-version",
                "9.4(3)",
                "--asdm-version",
                "7.6(1)",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"

    def test_should_fail_when_devices_have_wrong_asdm_and_no_asdm_flag(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        devices = _two_devices(asdm_version="7.5(2)")
        _patch_inventory(monkeypatch, devices)
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_cv("9.4(3)", "7.6(1)")])

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
                "9.4(3)",
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        assert "ASDM >= 7.6(1)" in result.output
        assert "2 device(s)" in result.output
        assert "--asdm-version=" in result.output

    def test_should_pass_when_devices_already_have_matching_asdm(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        devices = _two_devices(asdm_version="7.5(2)")
        _patch_inventory(monkeypatch, devices)
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_cv("9.4(2)", "7.5(2)")])

        def fake_upgrade_multiple(self: AsaUpgradeService, **kwargs: Any) -> CdoTransaction:
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
                "9.4(2)",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"

    def test_should_pass_when_device_asdm_in_compatible_set_without_flag(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Device already has a compatible ASDM — no --asdm-version needed."""
        device = _single_device(asdm_version="7.7(1)")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(
            monkeypatch,
            [_cv("9.4(3)", "7.6(1)"), _cv("9.4(3)", "7.7(1)"), _cv("9.4(3)", "7.8(2)")],
        )

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
                "--software-version",
                "9.4(3)",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"

    def test_should_skip_asdm_check_when_only_asdm_version_specified(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """ASDM-only upgrade validates against device's current Software version."""
        device = _single_device(asdm_version="7.5(2)", software_version="9.4(2)")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(
            monkeypatch,
            [_cv("9.4(2)", "7.5(2)"), _cv("9.4(2)", "7.18(1.152)")],
        )

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

    def test_should_skip_asdm_check_in_check_mode(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """--check mode should not trigger ASDM compat validation."""
        device = _single_device(asdm_version="7.5(2)")
        _patch_inventory(monkeypatch, [device])
        # Do NOT mock AsaUpgradeVersionService — it should not be called.

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
                "9.4(3)",
                "--check",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"


# ── ASDM downgrade validation tests ───────────────────────────


class TestAsdmDowngradeAllowed:
    """Tests that ASDM downgrade is allowed."""

    def test_should_allow_asdm_downgrade(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device(asdm_version="7.20(2)", software_version="9.4(2)")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(
            monkeypatch,
            [_cv("9.4(2)", "7.5(2)")],
        )
        monkeypatch.setattr(
            AsaUpgradeService,
            "upgrade_single",
            lambda self, **kw: _fake_transaction(),
        )

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
                "7.5(2)",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0


# ── Software downgrade validation tests ────────────────────────


class TestSoftwareDowngradeValidation:
    """Tests for software version downgrade prevention."""

    def test_should_fail_when_software_version_is_a_downgrade(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device(asdm_version="7.18(1.152)", software_version="9.18(4)")
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
                "--software-version",
                "9.4(3)",
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        assert "lower than the current" in result.output
        assert "Downgrades are not supported" in result.output

    def test_should_not_flag_software_upgrade(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device(asdm_version="7.18(1.152)", software_version="9.4(2)")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(
            monkeypatch,
            [_cv("9.18(4)", "7.18(1.152)")],
        )

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
                "--software-version",
                "9.18(4)",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"


class TestAsdmOnlyCompatibilityValidation:
    """Tests for ASDM compat checks when only --asdm-version is given."""

    def test_should_fail_when_asdm_not_compatible_with_current_sw(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device(asdm_version="7.5(2)", software_version="9.4(2)")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(
            monkeypatch,
            [_cv("9.4(2)", "7.5(2)"), _cv("9.4(2)", "7.6(1)")],
        )

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
                "7.24(1)",
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        assert "7.24(1) is not compatible" in result.output
        assert "9.4(2)" in result.output

    def test_should_pass_when_asdm_compatible_with_current_sw(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device(asdm_version="7.5(2)", software_version="9.4(2)")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(
            monkeypatch,
            [_cv("9.4(2)", "7.5(2)"), _cv("9.4(2)", "7.6(1)")],
        )

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
                "7.6(1)",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"


# ── Wait / transaction polling tests ──────────────────────────


def _stub_transaction_init(self: TransactionService, config: Any) -> None:
    return None


def _done_transaction(uid: str = "txn-waited") -> CdoTransaction:
    return CdoTransaction(
        transactionUid=uid,
        cdoTransactionStatus="DONE",
    )


def _error_transaction(uid: str = "txn-error") -> CdoTransaction:
    return CdoTransaction(
        transactionUid=uid,
        cdoTransactionStatus="ERROR",
        errorMessage="Upgrade failed: device unreachable",
    )


def _cancelled_transaction(uid: str = "txn-cancelled") -> CdoTransaction:
    return CdoTransaction(
        transactionUid=uid,
        cdoTransactionStatus="CANCELLED",
    )


def _patch_wait(monkeypatch: MonkeyPatch, result_transaction: CdoTransaction) -> None:
    """Stub TransactionService so wait_for_transaction_to_finish returns immediately."""
    monkeypatch.setattr(TransactionService, "__init__", _stub_transaction_init)
    monkeypatch.setattr(
        TransactionService,
        "wait_for_transaction_to_finish",
        lambda self, **kw: result_transaction,
    )


def _patch_single_trigger(monkeypatch: MonkeyPatch, txn: CdoTransaction) -> None:
    """Stub the upgrade service to return a given transaction."""
    monkeypatch.setattr(AsaUpgradeService, "__init__", _stub_upgrade_init)
    monkeypatch.setattr(
        AsaUpgradeService,
        "upgrade_single",
        lambda self, **kw: txn,
    )


class TestWaitForTransaction:
    """Tests for --wait / --timeout behaviour."""

    def test_wait_success_table(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device(asdm_version="7.18(1.152)")
        _patch_inventory(monkeypatch, [device])
        _patch_compatible_versions(monkeypatch, [_cv("9.18(4)", "7.18(1.152)")])

        pending = _fake_transaction("txn-wait-ok")
        done = _done_transaction("txn-wait-ok")

        _patch_single_trigger(monkeypatch, pending)
        _patch_wait(monkeypatch, done)

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
                "--wait",
                "--format",
                "table",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Upgrade triggered" in result.output
        assert "DONE" in result.output
        assert result.output.count("Transaction UID") == 1

    def test_wait_success_json_produces_valid_json(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Regression: --wait --format json must produce valid JSON on stdout."""
        device = _single_device(asdm_version="7.18(1.152)")
        _patch_inventory(monkeypatch, [device])
        _patch_compatible_versions(monkeypatch, [_cv("9.18(4)", "7.18(1.152)")])

        pending = _fake_transaction("txn-json-ok")
        done = _done_transaction("txn-json-ok")

        _patch_single_trigger(monkeypatch, pending)
        _patch_wait(monkeypatch, done)

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
                "--wait",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output)
        assert payload["transactionUid"] == "txn-json-ok"
        assert payload["cdoTransactionStatus"] == "DONE"

    def test_wait_error_table_shows_failure(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device(asdm_version="7.18(1.152)")
        _patch_inventory(monkeypatch, [device])
        _patch_compatible_versions(monkeypatch, [_cv("9.18(4)", "7.18(1.152)")])

        pending = _fake_transaction("txn-err")
        error = _error_transaction("txn-err")

        _patch_single_trigger(monkeypatch, pending)
        _patch_wait(monkeypatch, error)

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
                "--wait",
                "--format",
                "table",
            ],
        )

        assert result.exit_code != 0
        assert "failed" in result.output
        assert "Upgrade failed: device unreachable" in result.output

    def test_wait_error_json_produces_valid_json_with_nonzero_exit(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device(asdm_version="7.18(1.152)")
        _patch_inventory(monkeypatch, [device])
        _patch_compatible_versions(monkeypatch, [_cv("9.18(4)", "7.18(1.152)")])

        pending = _fake_transaction("txn-err-json")
        error = _error_transaction("txn-err-json")

        _patch_single_trigger(monkeypatch, pending)
        _patch_wait(monkeypatch, error)

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
                "--wait",
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        payload = json.loads(result.output)
        assert payload["cdoTransactionStatus"] == "ERROR"

    def test_wait_cancelled_is_reported_as_failure(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device(asdm_version="7.18(1.152)")
        _patch_inventory(monkeypatch, [device])
        _patch_compatible_versions(monkeypatch, [_cv("9.18(4)", "7.18(1.152)")])

        pending = _fake_transaction("txn-cancel")
        cancelled = _cancelled_transaction("txn-cancel")

        _patch_single_trigger(monkeypatch, pending)
        _patch_wait(monkeypatch, cancelled)

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
                "--wait",
                "--format",
                "table",
            ],
        )

        assert result.exit_code != 0
        assert "failed" in result.output

    def test_wait_timeout_raises_error(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device(asdm_version="7.18(1.152)")
        _patch_inventory(monkeypatch, [device])
        _patch_compatible_versions(monkeypatch, [_cv("9.18(4)", "7.18(1.152)")])

        pending = _fake_transaction("txn-timeout")

        _patch_single_trigger(monkeypatch, pending)
        monkeypatch.setattr(TransactionService, "__init__", _stub_transaction_init)

        def raise_timeout(**kw: Any) -> CdoTransaction:
            raise TimeoutError("Transaction txn-timeout did not complete within 5 seconds")

        monkeypatch.setattr(
            TransactionService,
            "wait_for_transaction_to_finish",
            lambda self, **kw: raise_timeout(**kw),
        )

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
                "--wait",
                "--timeout",
                "5",
                "--format",
                "table",
            ],
        )

        assert result.exit_code != 0
        assert "did not complete" in result.output
