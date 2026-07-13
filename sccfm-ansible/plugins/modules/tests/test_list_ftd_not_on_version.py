# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the list_ftd_not_on_version Ansible module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import list_ftd_not_on_version  # noqa: E402
from scc_firewall_manager_sdk import (
    ApiException,
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
    FtdVersion,
)

from cisco_sccfm_core.models.ftd_upgrade_version import FtdGroupCompatibleVersions

_TARGET_VERSION = "7.4.1"


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def device_on_target() -> Device:
    return Device(
        uid="uid-1",
        name="compliant-ftd",
        deviceType=EntityType.CDFMC_MANAGED_FTD,
        softwareVersion=_TARGET_VERSION,
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def device_off_target() -> Device:
    return Device(
        uid="uid-2",
        name="needs-upgrade-ftd",
        deviceType=EntityType.CDFMC_MANAGED_FTD,
        softwareVersion="7.2.0",
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def base_params() -> dict[str, Any]:
    return {
        "version": _TARGET_VERSION,
        "recommended": False,
        "query": None,
        "uids": None,
        "limit": 50,
        "offset": 0,
        "region": "us",
        "api_token": "test-token-123",
    }


def _mock_module(params: dict[str, Any]) -> MagicMock:
    mock = MagicMock()
    mock.params = params.copy()
    mock.check_mode = False
    mock.exit_json.side_effect = SystemExit(0)
    mock.fail_json.side_effect = SystemExit(1)
    return mock


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


# ── --version mode: basic filtering ──────────────────────────────


@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_version_mode_returns_devices_not_on_version(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
    device_on_target: Device,
    device_off_target: Device,
) -> None:
    params = {**base_params, "query": "name:prod-*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(
        count=2, limit=50, offset=0, items=[device_on_target, device_off_target]
    )
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is False
    assert kw["mode"] == "specified"
    assert kw["device_count"] == 1
    assert kw["matched_device_count"] == 2
    assert len(kw["devices"]) == 1
    assert kw["devices"][0]["uid"] == "uid-2"
    assert kw["devices"][0]["software_version"] == "7.2.0"


@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_version_mode_all_on_version(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
    device_on_target: Device,
) -> None:
    params = {**base_params, "query": "name:prod-*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[device_on_target]
    )
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    kw = mock_module.exit_json.call_args[1]
    assert kw["device_count"] == 0
    assert kw["devices"] == []
    assert f"All 1 evaluated device(s) are on version {_TARGET_VERSION}" in kw["msg"]


# ── --version mode: query construction ───────────────────────────


@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_version_mode_query_combines_with_ftd_device_types(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
) -> None:
    params = {**base_params, "query": "name:branch-*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=0, items=[])
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    call_kwargs = mock_inv.get_devices.call_args[1]
    assert "(name:branch-*)" in call_kwargs["query"]
    assert "deviceType:CDFMC_MANAGED_FTD" in call_kwargs["query"]


@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_version_mode_no_filter_queries_all_ftd_devices(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
) -> None:
    mock_module = _mock_module(base_params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=0, items=[])
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    call_kwargs = mock_inv.get_devices.call_args[1]
    assert "deviceType:CDFMC_MANAGED_FTD" in call_kwargs["query"]


@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_version_mode_uids_builds_uid_query(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
    device_off_target: Device,
) -> None:
    params = {**base_params, "uids": ["uid-2", "uid-3"]}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=1, items=[device_off_target])
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    call_kwargs = mock_inv.get_devices.call_args[1]
    assert "uid:uid-2" in call_kwargs["query"]
    assert "uid:uid-3" in call_kwargs["query"]


# ── --version mode: pagination ───────────────────────────────────


@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_version_mode_limit_and_offset_forwarded(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
) -> None:
    params = {**base_params, "query": "name:*", "limit": 25, "offset": 10}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=0, items=[])
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    call_kwargs = mock_inv.get_devices.call_args[1]
    assert call_kwargs["limit"] == 25
    assert call_kwargs["offset"] == 10


# ── --version mode: empty results ────────────────────────────────


@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_version_mode_no_devices_matched(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
) -> None:
    params = {**base_params, "query": "name:missing-*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=0, items=[])
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    kw = mock_module.exit_json.call_args[1]
    assert kw["devices"] == []
    assert kw["device_count"] == 0
    assert kw["matched_device_count"] == 0
    assert kw["msg"] == "No FTD devices matched the specified filter."


@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_version_mode_items_none_handled(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
) -> None:
    """DevicePage(items=None) is treated as zero devices."""
    mock_module = _mock_module(base_params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=0, items=None)
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    kw = mock_module.exit_json.call_args[1]
    assert kw["matched_device_count"] == 0
    assert kw["device_count"] == 0


# ── --recommended mode ───────────────────────────────────────────


@patch("plugins.modules.list_ftd_not_on_version.FtdUpgradeVersionService")
@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_recommended_mode_identifies_non_compliant(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    mock_upgrade_cls: MagicMock,
    base_params: dict[str, Any],
    device_off_target: Device,
) -> None:
    params = {**base_params, "version": None, "recommended": True}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=1, items=[device_off_target])
    mock_inventory_cls.return_value = mock_inv

    suggested = _fv("7.4.1", "pkg-1", suggested=True)
    mock_upgrade = MagicMock()
    mock_upgrade.get_compatible_versions.return_value = FtdGroupCompatibleVersions(
        per_device={"uid-2": [suggested]},
        common_versions=[suggested],
    )
    mock_upgrade_cls.return_value = mock_upgrade

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    kw = mock_module.exit_json.call_args[1]
    assert kw["mode"] == "recommended"
    assert kw["device_count"] == 1
    assert kw["devices"][0]["recommended_version"] == "7.4.1"
    assert kw["devices"][0]["software_version"] == "7.2.0"


@patch("plugins.modules.list_ftd_not_on_version.FtdUpgradeVersionService")
@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_recommended_mode_all_on_recommended(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    mock_upgrade_cls: MagicMock,
    base_params: dict[str, Any],
    device_on_target: Device,
) -> None:
    params = {**base_params, "version": None, "recommended": True}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=1, items=[device_on_target])
    mock_inventory_cls.return_value = mock_inv

    suggested = _fv("7.4.1", "pkg-1", suggested=True)
    mock_upgrade = MagicMock()
    mock_upgrade.get_compatible_versions.return_value = FtdGroupCompatibleVersions(
        per_device={"uid-1": [suggested]},
        common_versions=[suggested],
    )
    mock_upgrade_cls.return_value = mock_upgrade

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    kw = mock_module.exit_json.call_args[1]
    assert kw["device_count"] == 0
    assert kw["devices"] == []
    assert "All 1 evaluated device(s) are on their recommended version" in kw["msg"]


@patch("plugins.modules.list_ftd_not_on_version.FtdUpgradeVersionService")
@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_recommended_mode_all_skipped(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    mock_upgrade_cls: MagicMock,
    base_params: dict[str, Any],
    device_off_target: Device,
) -> None:
    """When all devices are skipped, report that none could be evaluated."""
    params = {**base_params, "version": None, "recommended": True}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=1, items=[device_off_target])
    mock_inventory_cls.return_value = mock_inv

    mock_upgrade = MagicMock()
    mock_upgrade.get_compatible_versions.return_value = FtdGroupCompatibleVersions(
        per_device={},
        common_versions=[],
        skipped={"uid-2": "Not a CDFMC_MANAGED_FTD device"},
    )
    mock_upgrade_cls.return_value = mock_upgrade

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    kw = mock_module.exit_json.call_args[1]
    assert kw["device_count"] == 0
    assert "were skipped" in kw["msg"]
    assert "uid-2" in kw["skipped"]


@patch("plugins.modules.list_ftd_not_on_version.FtdUpgradeVersionService")
@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_recommended_mode_skipped_no_suggested(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    mock_upgrade_cls: MagicMock,
    base_params: dict[str, Any],
    device_off_target: Device,
) -> None:
    """Devices with no suggested version are reported as skipped."""
    params = {**base_params, "version": None, "recommended": True}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=1, items=[device_off_target])
    mock_inventory_cls.return_value = mock_inv

    older = _fv("7.2.0", "pkg-2")
    mock_upgrade = MagicMock()
    mock_upgrade.get_compatible_versions.return_value = FtdGroupCompatibleVersions(
        per_device={"uid-2": [older]},
        common_versions=[],
    )
    mock_upgrade_cls.return_value = mock_upgrade

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    kw = mock_module.exit_json.call_args[1]
    assert kw["device_count"] == 0
    assert "uid-2" in kw["skipped"]
    assert kw["skipped"]["uid-2"] == "No recommended version available"


# ── Validation ────────────────────────────────────────────────────


@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_rejects_both_version_and_recommended(
    mock_ansible_cls: MagicMock,
    base_params: dict[str, Any],
) -> None:
    params = {**base_params, "recommended": True}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    mock_module.fail_json.assert_called_once()
    assert "not both" in mock_module.fail_json.call_args[1]["msg"]


@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_rejects_neither_version_nor_recommended(
    mock_ansible_cls: MagicMock,
    base_params: dict[str, Any],
) -> None:
    params = {**base_params, "version": None, "recommended": False}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    mock_module.fail_json.assert_called_once()
    assert "'version' or 'recommended'" in mock_module.fail_json.call_args[1]["msg"]


@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_rejects_invalid_version_format(
    mock_ansible_cls: MagicMock,
    base_params: dict[str, Any],
) -> None:
    params = {**base_params, "version": "not-a-version"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    mock_module.fail_json.assert_called_once()
    assert "Invalid version format" in mock_module.fail_json.call_args[1]["msg"]


# ── Error handling ────────────────────────────────────────────────


@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_fails_on_unexpected_exception(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
) -> None:
    params = {**base_params, "query": "name:*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.side_effect = Exception("Connection timeout")
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    mock_module.fail_json.assert_called_once()
    assert "Connection timeout" in mock_module.fail_json.call_args[1]["msg"]


@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_fails_on_api_exception(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
) -> None:
    params = {**base_params, "query": "name:*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    api_error = ApiException(status=403, reason="Forbidden")
    api_error.body = '{"errorMsg": "Access denied", "errorCode": "FORBIDDEN", "details": {}}'
    mock_inv = MagicMock()
    mock_inv.get_devices.side_effect = api_error
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert kw["msg"] == "Access denied"
    assert kw["error_code"] == "FORBIDDEN"
    assert kw["status_code"] == 403


# ── Idempotency ──────────────────────────────────────────────────


@patch("plugins.modules.list_ftd_not_on_version.create_config")
@patch("plugins.modules.list_ftd_not_on_version.InventoryService")
@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_never_reports_changed(
    mock_ansible_cls: MagicMock,
    mock_inventory_cls: MagicMock,
    _mock_config: MagicMock,
    base_params: dict[str, Any],
    device_off_target: Device,
) -> None:
    params = {**base_params, "query": "name:*"}
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=1, items=[device_off_target])
    mock_inventory_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        list_ftd_not_on_version.run_module()

    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is False


# ── Auth validation ──────────────────────────────────────────────


@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_fails_if_region_not_provided(
    mock_ansible_cls: MagicMock,
    base_params: dict[str, Any],
) -> None:
    params = {**base_params}
    del params["region"]
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            list_ftd_not_on_version.run_module()

    mock_module.fail_json.assert_called_once()
    assert "region is required" in mock_module.fail_json.call_args[1]["msg"]


@patch("plugins.modules.list_ftd_not_on_version.AnsibleModule")
def test_fails_if_api_token_not_provided(
    mock_ansible_cls: MagicMock,
    base_params: dict[str, Any],
) -> None:
    params = {**base_params}
    del params["api_token"]
    mock_module = _mock_module(params)
    mock_ansible_cls.return_value = mock_module

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            list_ftd_not_on_version.run_module()

    mock_module.fail_json.assert_called_once()
    assert "api_token is required" in mock_module.fail_json.call_args[1]["msg"]
