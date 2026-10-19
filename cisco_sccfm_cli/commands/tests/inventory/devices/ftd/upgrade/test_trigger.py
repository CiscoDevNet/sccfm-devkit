# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the ``cisco_sccfm_cli inventory devices ftd upgrade trigger`` command."""

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import (
    CdoTransaction,
    Device,
    DevicePage,
    EntityType,
    FtdVersion,
)

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.models import Config
from cisco_sccfm_core.models.ftd_upgrade_version import FtdGroupCompatibleVersions
from cisco_sccfm_core.services import InventoryService
from cisco_sccfm_core.services.inventory import FtdUpgradeService, FtdUpgradeVersionService


def _fake_transaction(uid: str = "txn-1") -> CdoTransaction:
    return CdoTransaction(
        transactionUid=uid,
        cdoTransactionStatus="PENDING",
    )


def _single_device(software_version: str | None = None) -> Device:
    return Device(
        uid="uid-1",
        name="ftd-01",
        deviceType=EntityType.CDFMC_MANAGED_FTD,
        softwareVersion=software_version,
    )


def _two_devices(software_version: str | None = None) -> list[Device]:
    return [
        Device(
            uid="uid-1",
            name="ftd-01",
            deviceType=EntityType.CDFMC_MANAGED_FTD,
            softwareVersion=software_version,
        ),
        Device(
            uid="uid-2",
            name="ftd-02",
            deviceType=EntityType.CDFMC_MANAGED_FTD,
            softwareVersion=software_version,
        ),
    ]


def _fv(sw: str, pkg_uid: str = "") -> FtdVersion:
    return FtdVersion(
        softwareVersion=sw,
        upgradePackageUid=pkg_uid,
        upgradeType="UPGRADE",
        filename=f"ftd-{sw}.pkg",
        isSuggestedVersion=False,
    )


# ── Helpers ─────────────────────────────────────────────────────


def _stub_upgrade_init(self: FtdUpgradeService, config: Any) -> None:
    return None


def _stub_version_init(self: FtdUpgradeVersionService, config: Any) -> None:
    return None


def _patch_compatible_versions(
    monkeypatch: MonkeyPatch,
    common_versions: list[FtdVersion],
) -> None:
    monkeypatch.setattr(FtdUpgradeVersionService, "__init__", _stub_version_init)

    def fake_get(
        self: FtdUpgradeVersionService, device_uids: list[str]
    ) -> FtdGroupCompatibleVersions:
        per_device = {uid: list(common_versions) for uid in device_uids}
        return FtdGroupCompatibleVersions(per_device=per_device, common_versions=common_versions)

    monkeypatch.setattr(FtdUpgradeVersionService, "get_compatible_versions", fake_get)


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
        monkeypatch.setattr(FtdUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_fv("7.4.1", "pkg-abc")])

        captured: dict[str, Any] = {}

        def fake_upgrade_single(self: FtdUpgradeService, **kwargs: Any) -> CdoTransaction:
            captured.update(kwargs)
            return _fake_transaction("txn-single")

        monkeypatch.setattr(FtdUpgradeService, "upgrade_single", fake_upgrade_single)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "ftd",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "--software-version",
                "7.4.1",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["transactionUid"] == "txn-single"
        assert captured["device_uid"] == "uid-1"
        assert captured["upgrade_package_uid"] == "pkg-abc"

    def test_should_trigger_staged_upgrade(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(FtdUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_fv("7.4.1", "pkg-abc")])

        captured: dict[str, Any] = {}

        def fake_upgrade_single(self: FtdUpgradeService, **kwargs: Any) -> CdoTransaction:
            captured.update(kwargs)
            return _fake_transaction()

        monkeypatch.setattr(FtdUpgradeService, "upgrade_single", fake_upgrade_single)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "ftd",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "--software-version",
                "7.4.1",
                "--stage-upgrade",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        assert captured["stage_upgrade"] is True


class TestMultipleDeviceTrigger:
    def test_should_trigger_multiple_upgrade_json(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        devices = _two_devices()
        _patch_inventory(monkeypatch, devices)
        monkeypatch.setattr(FtdUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_fv("7.4.1", "pkg-abc")])

        captured: dict[str, Any] = {}

        def fake_upgrade_multiple(self: FtdUpgradeService, **kwargs: Any) -> CdoTransaction:
            captured.update(kwargs)
            return _fake_transaction("txn-multi")

        monkeypatch.setattr(FtdUpgradeService, "upgrade_multiple", fake_upgrade_multiple)

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "ftd",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "-u",
                "uid-2",
                "--software-version",
                "7.4.1",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["transactionUid"] == "txn-multi"
        assert captured["device_uids"] == ["uid-1", "uid-2"]
        assert captured["upgrade_package_uid"] == "pkg-abc"


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
                "ftd",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "--software-version",
                "7.4.1",
                "--check",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["can_proceed"] is True
        assert data["matched_devices"] == 1


class TestDowngradeValidation:
    def test_should_fail_on_software_downgrade(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device(software_version="7.4.1")
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(FtdUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_fv("7.2.5", "pkg-old")])

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "ftd",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "--software-version",
                "7.2.5",
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        assert "Downgrades are not supported" in result.output


class TestVersionCompatibility:
    def test_should_fail_when_version_not_compatible(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        mock_inventory_service: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        device = _single_device()
        _patch_inventory(monkeypatch, [device])
        monkeypatch.setattr(FtdUpgradeService, "__init__", _stub_upgrade_init)
        _patch_compatible_versions(monkeypatch, [_fv("7.4.1", "pkg-abc")])

        result = cli_runner.invoke(
            cli,
            [
                "inventory",
                "devices",
                "ftd",
                "upgrade",
                "trigger",
                "-u",
                "uid-1",
                "--software-version",
                "7.6.0",
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        assert "not compatible" in result.output
