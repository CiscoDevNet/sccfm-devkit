# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for sccfm_cli inventory devices ftd list-not-on-version command."""

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import (
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
    FtdVersion,
)

from sccfm_cli.cli import cli
from sccfm_cli.models import Config
from sccfm_core.models.ftd_upgrade_version import FtdGroupCompatibleVersions
from sccfm_core.services import InventoryService
from sccfm_core.services.inventory import FtdUpgradeVersionService

_TARGET_VERSION = "7.4.1"

_CLI_PREFIX = ["inventory", "devices", "ftd", "list-not-on-version"]


def _sample_ftd_devices() -> list[Device]:
    return [
        Device(
            uid="uid-1",
            name="branch-ftd-01",
            device_type=EntityType.CDFMC_MANAGED_FTD,
            software_version="7.2.0",
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
        Device(
            uid="uid-2",
            name="branch-ftd-02",
            device_type=EntityType.CDFMC_MANAGED_FTD,
            software_version="7.0.1",
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
    ]


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


def _patch_inventory(
    monkeypatch: MonkeyPatch,
    devices: list[Device],
    captured: dict[str, Any] | None = None,
) -> None:
    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        if captured is not None:
            captured["query"] = query
            captured["limit"] = limit
            captured["offset"] = offset
        return DevicePage(count=len(devices), items=devices)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)


def _patch_upgrade_version_service(
    monkeypatch: MonkeyPatch,
    results: FtdGroupCompatibleVersions,
) -> None:
    def stub_init(self: FtdUpgradeVersionService, config: Any) -> None:
        return None

    def fake_get_compatible_versions(
        self: FtdUpgradeVersionService, device_uids: list[str]
    ) -> FtdGroupCompatibleVersions:
        return results

    monkeypatch.setattr(FtdUpgradeVersionService, "__init__", stub_init)
    monkeypatch.setattr(
        FtdUpgradeVersionService, "get_compatible_versions", fake_get_compatible_versions
    )


# ── --version mode: JSON output ──────────────────────────────────


def test_version_mode_returns_devices_as_json(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    _patch_inventory(monkeypatch, _sample_ftd_devices())

    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX, "--version", _TARGET_VERSION, "--format", "json"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    payload = json.loads(result.output)
    assert payload["mode"] == "specified"
    assert payload["version"] == _TARGET_VERSION
    assert payload["matched_device_count"] == 2
    assert payload["device_count"] == 2
    assert len(payload["devices"]) == 2
    assert payload["devices"][0]["uid"] == "uid-1"
    assert payload["devices"][0]["software_version"] == "7.2.0"


# ── --version mode: Table output ─────────────────────────────────


def test_version_mode_returns_devices_as_table(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    _patch_inventory(monkeypatch, _sample_ftd_devices())

    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX, "--version", _TARGET_VERSION],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "branch-ftd-01" in result.output
    assert "7.2.0" in result.output


# ── --version mode: Filters matching devices ─────────────────────


def test_version_mode_filters_out_matching_version(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    devices_with_target = [
        *_sample_ftd_devices(),
        Device(
            uid="uid-3",
            name="up-to-date-ftd",
            device_type=EntityType.CDFMC_MANAGED_FTD,
            software_version=_TARGET_VERSION,
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
    ]
    _patch_inventory(monkeypatch, devices_with_target)

    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX, "--version", _TARGET_VERSION, "--format", "json"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    payload = json.loads(result.output)
    assert payload["matched_device_count"] == 3
    assert payload["device_count"] == 2
    uids = [d["uid"] for d in payload["devices"]]
    assert "uid-3" not in uids
    assert "uid-1" in uids


# ── --version mode: Query filters by FTD device types ────────────


def test_version_mode_query_filters_by_ftd_device_type(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    _patch_inventory(monkeypatch, [], captured=captured)

    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX, "--version", _TARGET_VERSION, "--format", "json"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "deviceType:" in captured["query"]


# ── --version mode: Passes limit and offset ──────────────────────


def test_version_mode_passes_limit_and_offset(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    _patch_inventory(monkeypatch, [], captured=captured)

    result = cli_runner.invoke(
        cli,
        [
            *_CLI_PREFIX,
            "--version",
            _TARGET_VERSION,
            "--limit",
            "25",
            "--offset",
            "10",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert captured["limit"] == 25
    assert captured["offset"] == 10


# ── --version mode: Empty results ────────────────────────────────


def test_version_mode_handles_empty_results(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    _patch_inventory(monkeypatch, [])

    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX, "--version", _TARGET_VERSION, "--query", "name:missing-*"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "No FTD devices matched the given filter." in result.output


# ── --version mode: DevicePage returns items=None ─────────────────


def test_version_mode_handles_device_page_items_none(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """DevicePage(items=None) must not crash; treated as zero devices."""

    def fake_get_devices(
        self: InventoryService, *, limit: int, offset: int, query: str | None = None
    ) -> DevicePage:
        return DevicePage(count=0, items=None)

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)

    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX, "--version", _TARGET_VERSION, "--format", "json"],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    payload = json.loads(result.output)
    assert payload["matched_device_count"] == 0
    assert payload["device_count"] == 0


# ── --version mode: All compliant ────────────────────────────────


def test_version_mode_all_compliant_devices(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    all_on_target = [
        Device(
            uid="uid-1",
            name="compliant-ftd",
            device_type=EntityType.CDFMC_MANAGED_FTD,
            software_version=_TARGET_VERSION,
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
    ]
    _patch_inventory(monkeypatch, all_on_target)

    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX, "--version", _TARGET_VERSION],
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert f"All 1 evaluated device(s) are on version {_TARGET_VERSION}" in result.output


# ── --recommended mode: Identifies non-compliant devices ─────────


def test_recommended_mode_identifies_devices_not_on_suggested(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    devices = _sample_ftd_devices()
    _patch_inventory(monkeypatch, devices)

    suggested = _fv("7.4.1", "pkg-1", suggested=True)
    older = _fv("7.2.0", "pkg-2")
    group_versions = FtdGroupCompatibleVersions(
        per_device={
            "uid-1": [suggested, older],
            "uid-2": [suggested, older],
        },
        common_versions=[suggested, older],
    )
    _patch_upgrade_version_service(monkeypatch, group_versions)

    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX, "--recommended", "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "recommended"
    assert payload["matched_device_count"] == 2
    assert payload["device_count"] == 2
    assert payload["devices"][0]["recommended_version"] == "7.4.1"
    assert payload["devices"][0]["software_version"] == "7.2.0"


# ── --recommended mode: All on recommended ───────────────────────


def test_recommended_mode_all_on_recommended(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    devices = [
        Device(
            uid="uid-1",
            name="compliant-ftd",
            device_type=EntityType.CDFMC_MANAGED_FTD,
            software_version="7.4.1",
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
    ]
    _patch_inventory(monkeypatch, devices)

    suggested = _fv("7.4.1", "pkg-1", suggested=True)
    group_versions = FtdGroupCompatibleVersions(
        per_device={"uid-1": [suggested]},
        common_versions=[suggested],
    )
    _patch_upgrade_version_service(monkeypatch, group_versions)

    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX, "--recommended"],
    )

    assert result.exit_code == 0, result.output
    assert "All 1 evaluated device(s) are on their recommended version" in result.output


# ── --recommended mode: Handles skipped devices ──────────────────


def test_recommended_mode_handles_no_suggested_version(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    devices = _sample_ftd_devices()
    _patch_inventory(monkeypatch, devices)

    # uid-1 has no suggested version, uid-2 is skipped by API
    older = _fv("7.2.0", "pkg-2")
    group_versions = FtdGroupCompatibleVersions(
        per_device={"uid-1": [older]},
        common_versions=[],
        skipped={"uid-2": "Unsupported device type"},
    )
    _patch_upgrade_version_service(monkeypatch, group_versions)

    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX, "--recommended", "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["device_count"] == 0
    # JSON skipped keys use UID only
    assert "uid-2" in payload["skipped"]
    assert "uid-1" in payload["skipped"]


# ── --recommended mode: All devices skipped ──────────────────────


def test_recommended_mode_all_devices_skipped(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """When every matched device is skipped, do not report a false success."""
    devices = [
        Device(
            uid="uid-1",
            name="unsupported-ftd",
            device_type=EntityType.CDFMC_MANAGED_FTD,
            software_version="7.2.0",
            connectivity_state=ConnectivityState.ONLINE,
            config_state=ConfigState.SYNCED,
        ),
    ]
    _patch_inventory(monkeypatch, devices)

    group_versions = FtdGroupCompatibleVersions(
        per_device={},
        common_versions=[],
        skipped={"uid-1": "Device uid-1 is not a CDFMC_MANAGED_FTD device"},
    )
    _patch_upgrade_version_service(monkeypatch, group_versions)

    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX, "--recommended"],
    )

    assert result.exit_code == 0, result.output
    assert "were skipped" in result.output
    assert "All" not in result.output or "are on" not in result.output


# ── --recommended mode: Table output ─────────────────────────────


def test_recommended_mode_table_shows_recommended_column(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    devices = _sample_ftd_devices()
    _patch_inventory(monkeypatch, devices)

    suggested = _fv("7.4.1", "pkg-1", suggested=True)
    group_versions = FtdGroupCompatibleVersions(
        per_device={
            "uid-1": [suggested],
            "uid-2": [suggested],
        },
        common_versions=[suggested],
    )
    _patch_upgrade_version_service(monkeypatch, group_versions)

    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX, "--recommended"],
    )

    assert result.exit_code == 0, result.output
    # Rich may wrap "Recommended Version" across lines; check for partial match
    assert "Recommended" in result.output
    assert "branch-ftd-01" in result.output or "branch-ftd" in result.output


# ── Validation: Rejects both --version and --recommended ─────────


def test_rejects_both_version_and_recommended(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX, "--version", _TARGET_VERSION, "--recommended"],
    )

    assert result.exit_code != 0
    assert "not both" in result.output


# ── Validation: Rejects neither --version nor --recommended ──────


def test_rejects_missing_mode(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX],
    )

    assert result.exit_code != 0
    assert "--version or --recommended" in result.output


# ── Validation: Invalid version format ───────────────────────────


def test_rejects_invalid_version_format(
    cli_runner: CliRunner,
    default_config: Config,
) -> None:
    result = cli_runner.invoke(
        cli,
        [*_CLI_PREFIX, "--version", "not-a-version"],
    )

    assert result.exit_code != 0
    assert "Invalid version format" in result.output


# ── Validation: Rejects conflicting device filters ───────────────


def test_rejects_both_device_name_and_query(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
) -> None:
    _patch_inventory(monkeypatch, [])

    result = cli_runner.invoke(
        cli,
        [
            *_CLI_PREFIX,
            "--version",
            _TARGET_VERSION,
            "--device-name",
            "branch-*",
            "--query",
            "name:edge-*",
        ],
    )

    assert result.exit_code != 0
    assert "Provide only one of" in result.output
