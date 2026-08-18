# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import list_ftd_compatible_versions  # noqa: E402
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


@pytest.fixture
def sample_device() -> Device:
    return Device(
        uid="d4e5f6a7-b8c9-0123-def4-567890abcdef",
        name="test-ftd-01",
        deviceType=EntityType.CDFMC_MANAGED_FTD,
        softwareVersion="7.2.5",
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def sample_single_versions() -> FtdGroupCompatibleVersions:
    v1 = FtdVersion(
        softwareVersion="7.4.1",
        upgradePackageUid="pkg-abc-123",
        upgradeType="UPGRADE",
        filename="ftd-7.4.1.pkg",
        isSuggestedVersion=True,
    )
    return FtdGroupCompatibleVersions(
        per_device={"d4e5f6a7-b8c9-0123-def4-567890abcdef": [v1]},
        common_versions=[v1],
    )


@pytest.fixture
def sample_group_versions() -> FtdGroupCompatibleVersions:
    v1 = FtdVersion(
        softwareVersion="7.4.1",
        upgradePackageUid="pkg-abc-123",
        upgradeType="UPGRADE",
        filename="ftd-7.4.1.pkg",
        isSuggestedVersion=True,
    )
    return FtdGroupCompatibleVersions(
        per_device={
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890": [v1],
            "b2c3d4e5-f6a7-8901-bcde-f12345678901": [v1],
        },
        common_versions=[v1],
    )


@pytest.fixture
def sample_group_versions_with_skipped(
    sample_group_versions: FtdGroupCompatibleVersions,
) -> FtdGroupCompatibleVersions:
    return FtdGroupCompatibleVersions(
        per_device=sample_group_versions.per_device,
        common_versions=sample_group_versions.common_versions,
        skipped={"skipped-device": "Unsupported device type"},
    )


@pytest.fixture
def base_module_params_with_query() -> dict[str, Any]:
    return {
        "query": "name:test-*",
        "uids": None,
        "limit": 50,
        "offset": 0,
        "per_device": False,
        "profile": "default",
    }


@pytest.fixture
def base_module_params_with_uids() -> dict[str, Any]:
    return {
        "query": None,
        "uids": [
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        ],
        "limit": 50,
        "offset": 0,
        "per_device": False,
        "profile": "default",
    }


@pytest.fixture
def mock_module_instance_query(base_module_params_with_query: dict[str, Any]) -> MagicMock:
    mock_module = MagicMock()
    mock_module.params = base_module_params_with_query.copy()
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


@pytest.fixture
def mock_module_instance_uids(base_module_params_with_uids: dict[str, Any]) -> MagicMock:
    mock_module = MagicMock()
    mock_module.params = base_module_params_with_uids.copy()
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


@patch("plugins.modules.list_ftd_compatible_versions.create_config")
@patch("plugins.modules.list_ftd_compatible_versions.FtdUpgradeVersionService")
@patch("plugins.modules.list_ftd_compatible_versions.InventoryService")
@patch("plugins.modules.list_ftd_compatible_versions.AnsibleModule")
def test_should_return_compatible_versions_with_query(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_upgrade_service_class: MagicMock,
    _mock_create_config: MagicMock,
    mock_module_instance_query: MagicMock,
    sample_device: Device,
    sample_single_versions: FtdGroupCompatibleVersions,
) -> None:
    """run_module should return compatible versions for devices matching query."""
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_upgrade = MagicMock()
    mock_upgrade.get_compatible_versions.return_value = sample_single_versions
    mock_upgrade_service_class.return_value = mock_upgrade

    with pytest.raises(SystemExit):
        list_ftd_compatible_versions.run_module()

    mock_module_instance_query.exit_json.assert_called_once()
    call_kwargs = mock_module_instance_query.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert len(call_kwargs["compatible_versions"]) == 1
    assert call_kwargs["compatible_versions"][0]["software_version"] == "7.4.1"
    assert call_kwargs["compatible_versions"][0]["upgrade_package_uid"] == "pkg-abc-123"
    assert "common_versions" not in call_kwargs
    assert "per_device" not in call_kwargs


@patch("plugins.modules.list_ftd_compatible_versions.create_config")
@patch("plugins.modules.list_ftd_compatible_versions.FtdUpgradeVersionService")
@patch("plugins.modules.list_ftd_compatible_versions.InventoryService")
@patch("plugins.modules.list_ftd_compatible_versions.AnsibleModule")
def test_should_return_compatible_versions_with_uids_without_inventory_lookup(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_upgrade_service_class: MagicMock,
    _mock_create_config: MagicMock,
    mock_module_instance_uids: MagicMock,
    sample_group_versions: FtdGroupCompatibleVersions,
) -> None:
    """run_module should use UIDs directly without inventory lookup."""
    mock_ansible_module_class.return_value = mock_module_instance_uids

    mock_upgrade = MagicMock()
    mock_upgrade.get_compatible_versions.return_value = sample_group_versions
    mock_upgrade_service_class.return_value = mock_upgrade

    with pytest.raises(SystemExit):
        list_ftd_compatible_versions.run_module()

    mock_inventory_service_class.assert_not_called()

    mock_module_instance_uids.exit_json.assert_called_once()
    call_kwargs = mock_module_instance_uids.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert "2 device(s)" in call_kwargs["msg"]
    assert "common_versions" in call_kwargs
    assert "per_device" not in call_kwargs


@patch("plugins.modules.list_ftd_compatible_versions.create_config")
@patch("plugins.modules.list_ftd_compatible_versions.InventoryService")
@patch("plugins.modules.list_ftd_compatible_versions.AnsibleModule")
def test_should_fail_if_no_devices_found(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    _mock_create_config: MagicMock,
    mock_module_instance_query: MagicMock,
) -> None:
    """run_module should fail when no devices match the query."""
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(count=0, limit=50, offset=0, items=[])
    mock_inventory_service_class.return_value = mock_inventory

    with pytest.raises(SystemExit):
        list_ftd_compatible_versions.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "No devices found" in call_kwargs["msg"]


@patch("plugins.modules.list_ftd_compatible_versions.create_config")
@patch("plugins.modules.list_ftd_compatible_versions.FtdUpgradeVersionService")
@patch("plugins.modules.list_ftd_compatible_versions.InventoryService")
@patch("plugins.modules.list_ftd_compatible_versions.AnsibleModule")
def test_should_fail_on_unexpected_exception(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_upgrade_service_class: MagicMock,
    _mock_create_config: MagicMock,
    mock_module_instance_query: MagicMock,
    sample_device: Device,
) -> None:
    """run_module should fail on unexpected exceptions."""
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_upgrade = MagicMock()
    mock_upgrade.get_compatible_versions.side_effect = Exception("Connection timeout")
    mock_upgrade_service_class.return_value = mock_upgrade

    with pytest.raises(SystemExit):
        list_ftd_compatible_versions.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "Connection timeout" in call_kwargs["msg"]


@patch("plugins.modules.list_ftd_compatible_versions.create_config")
@patch("plugins.modules.list_ftd_compatible_versions.FtdUpgradeVersionService")
@patch("plugins.modules.list_ftd_compatible_versions.InventoryService")
@patch("plugins.modules.list_ftd_compatible_versions.AnsibleModule")
def test_should_return_structured_error_on_api_exception(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_upgrade_service_class: MagicMock,
    _mock_create_config: MagicMock,
    mock_module_instance_query: MagicMock,
    sample_device: Device,
) -> None:
    """run_module should return structured error info when ApiException occurs."""
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    api_error = ApiException(status=403, reason="Forbidden")
    api_error.body = (
        '{"errorMsg": "Access denied", "errorCode": "FORBIDDEN", "details": {"resource": "device"}}'
    )

    mock_upgrade = MagicMock()
    mock_upgrade.get_compatible_versions.side_effect = api_error
    mock_upgrade_service_class.return_value = mock_upgrade

    with pytest.raises(SystemExit):
        list_ftd_compatible_versions.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert call_kwargs["msg"] == "Access denied"
    assert call_kwargs["error_code"] == "FORBIDDEN"
    assert call_kwargs["status_code"] == 403


@patch("plugins.modules.list_ftd_compatible_versions.create_config")
@patch("plugins.modules.list_ftd_compatible_versions.FtdUpgradeVersionService")
@patch("plugins.modules.list_ftd_compatible_versions.InventoryService")
@patch("plugins.modules.list_ftd_compatible_versions.AnsibleModule")
def test_should_include_per_device_when_flag_set(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_upgrade_service_class: MagicMock,
    _mock_create_config: MagicMock,
    mock_module_instance_uids: MagicMock,
    sample_group_versions: FtdGroupCompatibleVersions,
) -> None:
    """run_module should include per_device breakdown when per_device=True."""
    mock_module_instance_uids.params["per_device"] = True
    mock_ansible_module_class.return_value = mock_module_instance_uids

    mock_upgrade = MagicMock()
    mock_upgrade.get_compatible_versions.return_value = sample_group_versions
    mock_upgrade_service_class.return_value = mock_upgrade

    with pytest.raises(SystemExit):
        list_ftd_compatible_versions.run_module()

    mock_module_instance_uids.exit_json.assert_called_once()
    call_kwargs = mock_module_instance_uids.exit_json.call_args[1]
    assert "common_versions" in call_kwargs
    assert "per_device" in call_kwargs


@patch("plugins.modules.list_ftd_compatible_versions.create_config")
@patch("plugins.modules.list_ftd_compatible_versions.FtdUpgradeVersionService")
@patch("plugins.modules.list_ftd_compatible_versions.AnsibleModule")
def test_should_include_skipped_devices_when_present(
    mock_ansible_module_class: MagicMock,
    mock_upgrade_service_class: MagicMock,
    _mock_create_config: MagicMock,
    mock_module_instance_uids: MagicMock,
    sample_group_versions_with_skipped: FtdGroupCompatibleVersions,
) -> None:
    """run_module should return skipped device reasons when the service provides them."""
    mock_ansible_module_class.return_value = mock_module_instance_uids

    mock_upgrade = MagicMock()
    mock_upgrade.get_compatible_versions.return_value = sample_group_versions_with_skipped
    mock_upgrade_service_class.return_value = mock_upgrade

    with pytest.raises(SystemExit):
        list_ftd_compatible_versions.run_module()

    call_kwargs = mock_module_instance_uids.exit_json.call_args[1]
    assert call_kwargs["skipped"] == {"skipped-device": "Unsupported device type"}
