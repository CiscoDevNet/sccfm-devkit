# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import list_asa_boot_registry  # noqa: E402
from scc_firewall_manager_sdk import (
    ApiException,
    CdoTransaction,
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
)

from sccfm_core.models.asa_boot_registry import AsaBootRegistry


@pytest.fixture
def sample_device() -> Device:
    return Device(
        uid="uid-1",
        name="asa-boot-1",
        deviceType=EntityType.ASA,
        softwareVersion="9.16.1",
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def sample_device_two() -> Device:
    return Device(
        uid="uid-2",
        name="asa-boot-2",
        deviceType=EntityType.ASA,
        softwareVersion="9.18.2",
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def sample_boot_registry() -> AsaBootRegistry:
    return AsaBootRegistry(
        system_image_file="disk0:/asa9191-41-lfbff-k8.SPA",
        compiled_date="Wed 13-Mar-24 02:50 GMT",
        config_register="0x1",
        config_modified=False,
        boot_system_entries=["disk0:/asa9191-41-lfbff-k8.SPA"],
    )


@pytest.fixture
def sample_boot_registry_two() -> AsaBootRegistry:
    return AsaBootRegistry(
        system_image_file="disk0:/asa9182-lfbff-k8.SPA",
        compiled_date="Fri 01-Jan-25 10:00 GMT",
        config_register="0x1",
        config_modified=True,
        boot_system_entries=[],
    )


@pytest.fixture
def query_params() -> dict[str, Any]:
    return {
        "query": "name:asa-*",
        "uids": None,
        "limit": 50,
        "offset": 0,
        "region": "us",
        "api_token": "test-token-123",
    }


@pytest.fixture
def uids_params() -> dict[str, Any]:
    return {
        "query": None,
        "uids": ["uid-1", "uid-2"],
        "limit": 50,
        "offset": 0,
        "region": "us",
        "api_token": "test-token-123",
    }


def _module_instance(params: dict[str, Any]) -> MagicMock:
    module = MagicMock()
    module.params = params.copy()
    module.exit_json.side_effect = SystemExit(0)
    module.fail_json.side_effect = SystemExit(1)
    return module


@patch("plugins.modules.list_asa_boot_registry.Config")
@patch("plugins.modules.list_asa_boot_registry.AsaBootRegistryService")
@patch("plugins.modules.list_asa_boot_registry.InventoryService")
@patch("plugins.modules.list_asa_boot_registry.AnsibleModule")
def test_should_return_boot_registry_with_query(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_boot_service_class: MagicMock,
    _mock_config_class: MagicMock,
    query_params: dict[str, Any],
    sample_device: Device,
    sample_boot_registry: AsaBootRegistry,
) -> None:
    mock_module = _module_instance(query_params)
    mock_ansible_module_class.return_value = mock_module

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_boot_service = MagicMock()
    mock_boot_service.list_boot_registry.return_value = {"uid-1": sample_boot_registry}
    mock_boot_service_class.return_value = mock_boot_service

    with pytest.raises(SystemExit):
        list_asa_boot_registry.run_module()

    mock_inventory.get_devices.assert_called_once()
    assert "deviceType:ASA" in mock_inventory.get_devices.call_args.kwargs["query"]

    mock_module.exit_json.assert_called_once()
    kwargs = mock_module.exit_json.call_args.kwargs
    assert kwargs["changed"] is False
    assert len(kwargs["results"]) == 1
    assert kwargs["results"][0]["device_uid"] == "uid-1"
    assert kwargs["results"][0]["system_image_file"] == "disk0:/asa9191-41-lfbff-k8.SPA"
    assert kwargs["results"][0]["config_register"] == "0x1"
    assert kwargs["results"][0]["config_modified"] is False
    assert kwargs["results"][0]["boot_system_entries"] == ["disk0:/asa9191-41-lfbff-k8.SPA"]
    assert "Successfully retrieved boot registry from 1 device(s)" in kwargs["msg"]


@patch("plugins.modules.list_asa_boot_registry.Config")
@patch("plugins.modules.list_asa_boot_registry.AsaBootRegistryService")
@patch("plugins.modules.list_asa_boot_registry.AnsibleModule")
def test_should_return_boot_registry_with_uids(
    mock_ansible_module_class: MagicMock,
    mock_boot_service_class: MagicMock,
    _mock_config_class: MagicMock,
    uids_params: dict[str, Any],
    sample_boot_registry: AsaBootRegistry,
    sample_boot_registry_two: AsaBootRegistry,
) -> None:
    mock_module = _module_instance(uids_params)
    mock_ansible_module_class.return_value = mock_module

    mock_boot_service = MagicMock()
    mock_boot_service.list_boot_registry.return_value = {
        "uid-1": sample_boot_registry,
        "uid-2": sample_boot_registry_two,
    }
    mock_boot_service_class.return_value = mock_boot_service

    with pytest.raises(SystemExit):
        list_asa_boot_registry.run_module()

    mock_module.exit_json.assert_called_once()
    kwargs = mock_module.exit_json.call_args.kwargs
    assert kwargs["changed"] is False
    assert len(kwargs["results"]) == 2
    assert kwargs["results"][0]["device_uid"] == "uid-1"
    assert kwargs["results"][1]["device_uid"] == "uid-2"
    assert kwargs["results"][1]["config_modified"] is True
    assert kwargs["results"][1]["boot_system_entries"] == []
    assert "Successfully retrieved boot registry from 2 device(s)" in kwargs["msg"]


@patch("plugins.modules.list_asa_boot_registry.Config")
@patch("plugins.modules.list_asa_boot_registry.InventoryService")
@patch("plugins.modules.list_asa_boot_registry.AnsibleModule")
def test_should_fail_when_no_devices_found(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    _mock_config_class: MagicMock,
    query_params: dict[str, Any],
) -> None:
    mock_module = _module_instance(query_params)
    mock_ansible_module_class.return_value = mock_module

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(count=0, limit=50, offset=0, items=[])
    mock_inventory_service_class.return_value = mock_inventory

    with pytest.raises(SystemExit):
        list_asa_boot_registry.run_module()

    kwargs = mock_module.fail_json.call_args.kwargs
    assert "No devices found matching the specified query." == kwargs["msg"]


@patch("plugins.modules.list_asa_boot_registry.Config")
@patch("plugins.modules.list_asa_boot_registry.AsaBootRegistryService")
@patch("plugins.modules.list_asa_boot_registry.InventoryService")
@patch("plugins.modules.list_asa_boot_registry.AnsibleModule")
def test_should_fail_when_transaction_is_returned(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_boot_service_class: MagicMock,
    _mock_config_class: MagicMock,
    query_params: dict[str, Any],
    sample_device: Device,
) -> None:
    mock_module = _module_instance(query_params)
    mock_ansible_module_class.return_value = mock_module

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_boot_service = MagicMock()
    mock_boot_service.list_boot_registry.return_value = CdoTransaction(
        transactionUid="tx-1",
        cdoTransactionStatus="ERROR",
        errorMessage="Device unreachable",
    )
    mock_boot_service_class.return_value = mock_boot_service

    with pytest.raises(SystemExit):
        list_asa_boot_registry.run_module()

    kwargs = mock_module.fail_json.call_args.kwargs
    assert kwargs["msg"] == "Boot registry retrieval failed with status: ERROR"
    assert kwargs["transaction_uid"] == "tx-1"
    assert kwargs["error_message"] == "Device unreachable"


@patch("plugins.modules.list_asa_boot_registry.Config")
@patch("plugins.modules.list_asa_boot_registry.AsaBootRegistryService")
@patch("plugins.modules.list_asa_boot_registry.InventoryService")
@patch("plugins.modules.list_asa_boot_registry.AnsibleModule")
def test_should_fail_on_api_exception(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_boot_service_class: MagicMock,
    _mock_config_class: MagicMock,
    query_params: dict[str, Any],
    sample_device: Device,
) -> None:
    mock_module = _module_instance(query_params)
    mock_ansible_module_class.return_value = mock_module

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_boot_service = MagicMock()
    mock_boot_service.list_boot_registry.side_effect = ApiException(status=403, reason="Forbidden")
    mock_boot_service_class.return_value = mock_boot_service

    with pytest.raises(SystemExit):
        list_asa_boot_registry.run_module()

    mock_module.fail_json.assert_called_once()
