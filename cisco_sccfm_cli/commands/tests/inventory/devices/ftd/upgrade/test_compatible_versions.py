# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import Device, DevicePage, EntityType, FtdVersion

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.models import Config
from cisco_sccfm_core.models.ftd_upgrade_version import FtdGroupCompatibleVersions
from cisco_sccfm_core.services import InventoryService
from cisco_sccfm_core.services.inventory import FtdUpgradeVersionService


def _fv(
    sw: str, pkg_uid: str = "", upgrade_type: str = "UPGRADE", suggested: bool = False
) -> FtdVersion:
    return FtdVersion(
        softwareVersion=sw,
        upgradePackageUid=pkg_uid,
        upgradeType=upgrade_type,
        filename=f"ftd-{sw}.pkg",
        isSuggestedVersion=suggested,
    )


def _sample_group_versions() -> FtdGroupCompatibleVersions:
    v1 = _fv("7.4.1", "pkg-1", suggested=True)
    v2 = _fv("7.2.5", "pkg-2")
    return FtdGroupCompatibleVersions(
        per_device={
            "uid-1": [v1, v2],
            "uid-2": [v1],
        },
        common_versions=[v1],
    )


def _ftd_devices() -> list[Device]:
    return [
        Device(uid="uid-1", name="ftd-01", deviceType=EntityType.CDFMC_MANAGED_FTD),
        Device(uid="uid-2", name="ftd-02", deviceType=EntityType.CDFMC_MANAGED_FTD),
    ]


def test_should_return_group_json_without_per_device_by_default(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Multi-device JSON should show common_versions only (no per_device) by default."""
    group_versions = _sample_group_versions()

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        devices = _ftd_devices()
        return DevicePage(count=len(devices), items=devices)

    def fake_get_compatible_versions(
        self: FtdUpgradeVersionService, device_uids: list[str]
    ) -> FtdGroupCompatibleVersions:
        return group_versions

    def stub_upgrade_init(self: FtdUpgradeVersionService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(
        FtdUpgradeVersionService, "get_compatible_versions", fake_get_compatible_versions
    )
    monkeypatch.setattr(FtdUpgradeVersionService, "__init__", stub_upgrade_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "ftd",
            "upgrade",
            "compatible-versions",
            "-u",
            "uid-1",
            "-u",
            "uid-2",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["device_count"] == 2
    assert "common_versions" in data
    assert "per_device" not in data
    assert len(data["common_versions"]) == 1
    assert data["common_versions"][0]["software_version"] == "7.4.1"
    assert data["common_versions"][0]["upgrade_package_uid"] == "pkg-1"


def test_should_return_single_device_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Single-device JSON should return flat structure with device_name."""
    v1 = _fv("7.4.1", "pkg-1", suggested=True)
    v2 = _fv("7.2.5", "pkg-2")
    group_versions = FtdGroupCompatibleVersions(
        per_device={"uid-1": [v1, v2]},
        common_versions=[v1, v2],
    )

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        device = Device(uid="uid-1", name="ftd-01", deviceType=EntityType.CDFMC_MANAGED_FTD)
        return DevicePage(count=1, items=[device])

    def fake_get_compatible_versions(
        self: FtdUpgradeVersionService, device_uids: list[str]
    ) -> FtdGroupCompatibleVersions:
        return group_versions

    def stub_upgrade_init(self: FtdUpgradeVersionService, config: Any) -> None:
        return None

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(
        FtdUpgradeVersionService, "get_compatible_versions", fake_get_compatible_versions
    )
    monkeypatch.setattr(FtdUpgradeVersionService, "__init__", stub_upgrade_init)

    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "ftd",
            "upgrade",
            "compatible-versions",
            "-u",
            "uid-1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["device_name"] == "ftd-01"
    assert len(data["compatible_versions"]) == 2


def test_should_fail_with_no_filters(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
) -> None:
    result = cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "ftd",
            "upgrade",
            "compatible-versions",
            "--format",
            "json",
        ],
    )
    assert result.exit_code != 0
