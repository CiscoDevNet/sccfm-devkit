# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import change_asa_boot_image  # noqa: E402
from scc_firewall_manager_sdk import (
    CdoTransaction,
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
)

from sccfm_core.models.asa_boot_image_change_result import AsaBootImageChangeResult

UID_1 = "11111111-1111-4111-8111-111111111111"
UID_2 = "22222222-2222-4222-8222-222222222222"
IMAGE_PATH = "disk0:/asa9-18-4-smp-k8.bin"


@pytest.fixture
def sample_ready_device() -> Device:
    return Device(
        uid=UID_1,
        name="asa-ready",
        deviceType=EntityType.ASA,
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def sample_not_ready_device() -> Device:
    return Device(
        uid=UID_2,
        name="asa-staging",
        deviceType=EntityType.ASA,
        connectivityState=ConnectivityState.UNREACHABLE,
        configState=ConfigState.NOT_SYNCED,
    )


@pytest.fixture
def base_module_params_with_query() -> dict[str, Any]:
    return {
        "query": "name:test-*",
        "uids": None,
        "image_path": IMAGE_PATH,
        "limit": 50,
        "offset": 0,
        "region": "us",
        "api_token": "test-token-123",
    }


@pytest.fixture
def base_module_params_with_uids() -> dict[str, Any]:
    return {
        "query": None,
        "uids": [UID_1, UID_2],
        "image_path": IMAGE_PATH,
        "limit": 50,
        "offset": 0,
        "region": "us",
        "api_token": "test-token-123",
    }


def _module_instance(params: dict[str, Any], *, check_mode: bool = False) -> MagicMock:
    module = MagicMock()
    module.params = params.copy()
    module.check_mode = check_mode
    module.exit_json.side_effect = SystemExit(0)
    module.fail_json.side_effect = SystemExit(1)
    return module


@patch("plugins.modules.change_asa_boot_image.AsaBootImageService")
@patch("plugins.modules.change_asa_boot_image.InventoryService")
@patch("plugins.modules.change_asa_boot_image.AnsibleModule")
def test_should_change_boot_image_with_query(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_boot_image_service_class: MagicMock,
    base_module_params_with_query: dict[str, Any],
    sample_ready_device: Device,
) -> None:
    mock_module = _module_instance(base_module_params_with_query)
    mock_ansible_module_class.return_value = mock_module

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_ready_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_service = MagicMock()
    mock_service.change_boot_image.return_value = {
        UID_1: AsaBootImageChangeResult(
            device_uid=UID_1,
            requested_image_path=IMAGE_PATH,
            status="success",
            message="Boot image changed successfully.",
            boot_system_entries_before=["disk0:/old.bin"],
            boot_system_entries_after=[IMAGE_PATH],
        )
    }
    mock_boot_image_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        change_asa_boot_image.run_module()

    mock_module.exit_json.assert_called_once()
    kwargs = mock_module.exit_json.call_args.kwargs
    assert kwargs["changed"] is True
    assert kwargs["results"][0]["status"] == "success"
    assert kwargs["results"][0]["device_name"] == "asa-ready"


@patch("plugins.modules.change_asa_boot_image.AsaBootImageService")
@patch("plugins.modules.change_asa_boot_image.InventoryService")
@patch("plugins.modules.change_asa_boot_image.AnsibleModule")
def test_should_resolve_devices_for_uids_and_include_not_ready_results(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_boot_image_service_class: MagicMock,
    base_module_params_with_uids: dict[str, Any],
    sample_ready_device: Device,
    sample_not_ready_device: Device,
) -> None:
    mock_module = _module_instance(base_module_params_with_uids)
    mock_ansible_module_class.return_value = mock_module

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=2,
        limit=50,
        offset=0,
        items=[sample_ready_device, sample_not_ready_device],
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_service = MagicMock()
    mock_service.change_boot_image.return_value = {
        UID_1: AsaBootImageChangeResult(
            device_uid=UID_1,
            requested_image_path=IMAGE_PATH,
            status="success",
            message="Boot image changed successfully.",
            boot_system_entries_before=[],
            boot_system_entries_after=[IMAGE_PATH],
        )
    }
    mock_boot_image_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        change_asa_boot_image.run_module()

    kwargs = mock_module.exit_json.call_args.kwargs
    assert kwargs["changed"] is True
    assert kwargs["results"][0]["status"] == "success"
    assert kwargs["results"][1]["status"] == "device_not_ready"


@patch("plugins.modules.change_asa_boot_image.AsaBootImageService")
@patch("plugins.modules.change_asa_boot_image.InventoryService")
@patch("plugins.modules.change_asa_boot_image.AnsibleModule")
def test_should_use_check_mode_and_report_changed_when_would_change(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_boot_image_service_class: MagicMock,
    base_module_params_with_query: dict[str, Any],
    sample_ready_device: Device,
) -> None:
    mock_module = _module_instance(base_module_params_with_query, check_mode=True)
    mock_ansible_module_class.return_value = mock_module

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_ready_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_service = MagicMock()
    mock_service.check_boot_image.return_value = {
        UID_1: AsaBootImageChangeResult(
            device_uid=UID_1,
            requested_image_path=IMAGE_PATH,
            status="would_change",
            message="Boot image would be changed to the requested image.",
            boot_system_entries_before=["disk0:/old.bin"],
            boot_system_entries_after=[IMAGE_PATH],
        )
    }
    mock_boot_image_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        change_asa_boot_image.run_module()

    kwargs = mock_module.exit_json.call_args.kwargs
    assert kwargs["changed"] is True
    assert kwargs["results"][0]["status"] == "would_change"


@patch("plugins.modules.change_asa_boot_image.AsaBootImageService")
@patch("plugins.modules.change_asa_boot_image.InventoryService")
@patch("plugins.modules.change_asa_boot_image.AnsibleModule")
def test_should_return_changed_false_when_only_non_mutating_statuses_exist(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_boot_image_service_class: MagicMock,
    base_module_params_with_query: dict[str, Any],
    sample_ready_device: Device,
) -> None:
    mock_module = _module_instance(base_module_params_with_query)
    mock_ansible_module_class.return_value = mock_module

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_ready_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_service = MagicMock()
    mock_service.change_boot_image.return_value = {
        UID_1: AsaBootImageChangeResult(
            device_uid=UID_1,
            requested_image_path=IMAGE_PATH,
            status="no_change",
            message="Requested image is already the sole configured boot image.",
            boot_system_entries_before=[IMAGE_PATH],
            boot_system_entries_after=[IMAGE_PATH],
        )
    }
    mock_boot_image_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        change_asa_boot_image.run_module()

    kwargs = mock_module.exit_json.call_args.kwargs
    assert kwargs["changed"] is False
    assert kwargs["results"][0]["status"] == "no_change"


@patch("plugins.modules.change_asa_boot_image.InventoryService")
@patch("plugins.modules.change_asa_boot_image.AnsibleModule")
def test_should_fail_if_no_devices_found(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    base_module_params_with_query: dict[str, Any],
) -> None:
    mock_module = _module_instance(base_module_params_with_query)
    mock_ansible_module_class.return_value = mock_module

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(count=0, limit=50, offset=0, items=[])
    mock_inventory_service_class.return_value = mock_inventory

    with pytest.raises(SystemExit):
        change_asa_boot_image.run_module()

    kwargs = mock_module.fail_json.call_args.kwargs
    assert "No devices found" in kwargs["msg"]


@patch("plugins.modules.change_asa_boot_image.AsaBootImageService")
@patch("plugins.modules.change_asa_boot_image.InventoryService")
@patch("plugins.modules.change_asa_boot_image.AnsibleModule")
def test_should_fail_if_service_returns_transaction(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_boot_image_service_class: MagicMock,
    base_module_params_with_query: dict[str, Any],
    sample_ready_device: Device,
) -> None:
    mock_module = _module_instance(base_module_params_with_query)
    mock_ansible_module_class.return_value = mock_module

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_ready_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_service = MagicMock()
    mock_service.change_boot_image.return_value = CdoTransaction(
        transactionUid="tx-123",
        cdoTransactionStatus="ERROR",
        errorMessage="Boot config update failed",
    )
    mock_boot_image_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        change_asa_boot_image.run_module()

    kwargs = mock_module.fail_json.call_args.kwargs
    assert kwargs["msg"] == "Boot image change failed with status: ERROR"
    assert kwargs["transaction_uid"] == "tx-123"


@patch("plugins.modules.change_asa_boot_image.AnsibleModule")
def test_should_fail_if_image_path_is_invalid(
    mock_ansible_module_class: MagicMock,
    base_module_params_with_query: dict[str, Any],
) -> None:
    params = base_module_params_with_query.copy()
    params["image_path"] = "asa9-18-4-smp-k8.bin"
    mock_module = _module_instance(params)
    mock_ansible_module_class.return_value = mock_module

    with pytest.raises(SystemExit):
        change_asa_boot_image.run_module()

    kwargs = mock_module.fail_json.call_args.kwargs
    assert "full device path" in kwargs["msg"]
