# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import list_asa_local_users  # noqa: E402
from scc_firewall_manager_sdk import (
    CdoCliResult,
    CdoTransaction,
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
)


@pytest.fixture
def sample_device() -> Device:
    return Device(
        uid="uid-1",
        name="asa-local-1",
        deviceType=EntityType.ASA,
        softwareVersion="9.16.1",
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def sample_device_two() -> Device:
    return Device(
        uid="uid-2",
        name="asa-local-2",
        deviceType=EntityType.ASA,
        softwareVersion="9.18.2",
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def sample_cli_result() -> CdoCliResult:
    return CdoCliResult(
        uid="result-1",
        device_uid="uid-1",
        result="User  Locked\nadmin  N",
        error_msg=None,
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


@patch("plugins.modules.list_asa_local_users.Config")
@patch("plugins.modules.list_asa_local_users.AsaCommandLineService")
@patch("plugins.modules.list_asa_local_users.InventoryService")
@patch("plugins.modules.list_asa_local_users.AnsibleModule")
def test_should_return_parsed_local_users_with_query(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_cli_service_class: MagicMock,
    _mock_config_class: MagicMock,
    query_params: dict[str, Any],
    sample_device: Device,
    sample_cli_result: CdoCliResult,
) -> None:
    mock_module = _module_instance(query_params)
    mock_ansible_module_class.return_value = mock_module

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_cli = MagicMock()
    mock_cli.execute_cli.return_value = [sample_cli_result]
    mock_cli_service_class.return_value = mock_cli

    with pytest.raises(SystemExit):
        list_asa_local_users.run_module()

    mock_inventory.get_devices.assert_called_once()
    assert "deviceType:ASA" in mock_inventory.get_devices.call_args.kwargs["query"]

    mock_module.exit_json.assert_called_once()
    kwargs = mock_module.exit_json.call_args.kwargs
    assert kwargs["changed"] is False
    assert kwargs["asa_local_users"] == {"asa-local-1": [{"user": "admin", "locked": "N"}]}
    assert json.loads(kwargs["asa_local_users_json"]) == kwargs["asa_local_users"]
    assert "Successfully retrieved local users from 1 device(s)" in kwargs["msg"]


@patch("plugins.modules.list_asa_local_users.Config")
@patch("plugins.modules.list_asa_local_users.AsaCommandLineService")
@patch("plugins.modules.list_asa_local_users.InventoryService")
@patch("plugins.modules.list_asa_local_users.AnsibleModule")
def test_should_resolve_uids_and_return_local_users(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_cli_service_class: MagicMock,
    _mock_config_class: MagicMock,
    uids_params: dict[str, Any],
    sample_device: Device,
    sample_device_two: Device,
) -> None:
    mock_module = _module_instance(uids_params)
    mock_ansible_module_class.return_value = mock_module

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=2, limit=2, offset=0, items=[sample_device, sample_device_two]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_cli = MagicMock()
    mock_cli.execute_cli.return_value = [
        CdoCliResult(uid="r1", device_uid="uid-1", result="User  Locked\nadmin  N", error_msg=None),
        CdoCliResult(uid="r2", device_uid="uid-2", result="User  Locked\nops  Y", error_msg=None),
    ]
    mock_cli_service_class.return_value = mock_cli

    with pytest.raises(SystemExit):
        list_asa_local_users.run_module()

    called_query = mock_inventory.get_devices.call_args.kwargs["query"]
    assert called_query == "uid:uid-1 OR uid:uid-2"

    kwargs = mock_module.exit_json.call_args.kwargs
    assert kwargs["asa_local_users"]["asa-local-1"] == [{"user": "admin", "locked": "N"}]
    assert kwargs["asa_local_users"]["asa-local-2"] == [{"user": "ops", "locked": "Y"}]
    assert json.loads(kwargs["asa_local_users_json"]) == kwargs["asa_local_users"]
    assert "Successfully retrieved local users from 2 device(s)" in kwargs["msg"]


@patch("plugins.modules.list_asa_local_users.Config")
@patch("plugins.modules.list_asa_local_users.InventoryService")
@patch("plugins.modules.list_asa_local_users.AnsibleModule")
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
        list_asa_local_users.run_module()

    kwargs = mock_module.fail_json.call_args.kwargs
    assert "No devices found matching the specified filter." == kwargs["msg"]


@patch("plugins.modules.list_asa_local_users.Config")
@patch("plugins.modules.list_asa_local_users.AsaCommandLineService")
@patch("plugins.modules.list_asa_local_users.InventoryService")
@patch("plugins.modules.list_asa_local_users.AnsibleModule")
def test_should_fail_when_transaction_is_returned(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_cli_service_class: MagicMock,
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

    mock_cli = MagicMock()
    mock_cli.execute_cli.return_value = CdoTransaction(
        transactionUid="tx-1",
        cdoTransactionStatus="ERROR",
        errorMessage="Device unreachable",
    )
    mock_cli_service_class.return_value = mock_cli

    with pytest.raises(SystemExit):
        list_asa_local_users.run_module()

    kwargs = mock_module.fail_json.call_args.kwargs
    assert kwargs["msg"] == "CLI execution failed with status: ERROR"
    assert kwargs["transaction_uid"] == "tx-1"
    assert kwargs["error_message"] == "Device unreachable"
