# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import change_asa_local_password  # noqa: E402
from scc_firewall_manager_sdk import (
    ApiException,
    CdoTransaction,
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
)

from cisco_sccfm_core.models.asa_password_change_result import AsaPasswordChangeResult


@pytest.fixture
def sample_device() -> Device:
    """Provides a sample ASA device for testing."""
    return Device(
        uid="d4e5f6a7-b8c9-0123-def4-567890abcdef",
        name="test-asa-01",
        deviceType=EntityType.ASA,
        softwareVersion="9.16.1",
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def sample_results() -> dict[str, AsaPasswordChangeResult]:
    """Provides sample password change results."""
    return {
        "uid-1": AsaPasswordChangeResult(
            device_uid="uid-1",
            status="success",
            message="Password changed successfully.",
        ),
    }


@pytest.fixture
def base_module_params_with_query() -> dict[str, Any]:
    """Provides base module parameters with query."""
    return {
        "query": "name:test-*",
        "uids": None,
        "username": "admin",
        "new_password": "NewSecurePass123",
        "limit": 50,
        "offset": 0,
        "region": "us",
        "api_token": "test-token-123",
    }


@pytest.fixture
def base_module_params_with_uids() -> dict[str, Any]:
    """Provides base module parameters with UIDs."""
    return {
        "query": None,
        "uids": ["uid-1", "uid-2"],
        "username": "admin",
        "new_password": "NewSecurePass123",
        "limit": 50,
        "offset": 0,
        "region": "us",
        "api_token": "test-token-123",
    }


@pytest.fixture
def mock_module_instance_query(base_module_params_with_query: dict[str, Any]) -> MagicMock:
    """Creates a mock module instance with query params."""
    mock_module = MagicMock()
    mock_module.params = base_module_params_with_query.copy()
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


@pytest.fixture
def mock_module_instance_uids(base_module_params_with_uids: dict[str, Any]) -> MagicMock:
    """Creates a mock module instance with UIDs params."""
    mock_module = MagicMock()
    mock_module.params = base_module_params_with_uids.copy()
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


@patch("plugins.modules.change_asa_local_password.Config")
@patch("plugins.modules.change_asa_local_password.AsaUserPasswordService")
@patch("plugins.modules.change_asa_local_password.InventoryService")
@patch("plugins.modules.change_asa_local_password.AnsibleModule")
def test_should_change_password_with_query(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_password_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_query: MagicMock,
    sample_device: Device,
    sample_results: dict[str, AsaPasswordChangeResult],
) -> None:
    """run_module should change password on devices matching query."""
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_password_svc = MagicMock()
    mock_password_svc.change_password.return_value = sample_results
    mock_password_service_class.return_value = mock_password_svc

    with pytest.raises(SystemExit):
        change_asa_local_password.run_module()

    mock_module_instance_query.exit_json.assert_called_once()
    call_kwargs = mock_module_instance_query.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert len(call_kwargs["results"]) == 1
    assert call_kwargs["results"][0]["status"] == "success"
    assert "Password change completed" in call_kwargs["msg"]


@patch("plugins.modules.change_asa_local_password.Config")
@patch("plugins.modules.change_asa_local_password.AsaUserPasswordService")
@patch("plugins.modules.change_asa_local_password.AnsibleModule")
def test_should_change_password_with_uids_without_inventory_lookup(
    mock_ansible_module_class: MagicMock,
    mock_password_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_uids: MagicMock,
    sample_results: dict[str, AsaPasswordChangeResult],
) -> None:
    """run_module should change password using UIDs directly."""
    mock_ansible_module_class.return_value = mock_module_instance_uids

    mock_password_svc = MagicMock()
    mock_password_svc.change_password.return_value = sample_results
    mock_password_service_class.return_value = mock_password_svc

    with pytest.raises(SystemExit):
        change_asa_local_password.run_module()

    mock_module_instance_uids.exit_json.assert_called_once()
    call_kwargs = mock_module_instance_uids.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert "2 device(s)" in call_kwargs["msg"]


@patch("plugins.modules.change_asa_local_password.Config")
@patch("plugins.modules.change_asa_local_password.InventoryService")
@patch("plugins.modules.change_asa_local_password.AnsibleModule")
def test_should_fail_if_no_devices_found(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_query: MagicMock,
) -> None:
    """run_module should fail when no devices match the query."""
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(count=0, limit=50, offset=0, items=[])
    mock_inventory_service_class.return_value = mock_inventory

    with pytest.raises(SystemExit):
        change_asa_local_password.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "No devices found" in call_kwargs["msg"]


@patch("plugins.modules.change_asa_local_password.Config")
@patch("plugins.modules.change_asa_local_password.AsaUserPasswordService")
@patch("plugins.modules.change_asa_local_password.InventoryService")
@patch("plugins.modules.change_asa_local_password.AnsibleModule")
def test_should_fail_if_transaction_returns_error(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_password_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_query: MagicMock,
    sample_device: Device,
) -> None:
    """run_module should fail when service returns a failed transaction."""
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    failed_transaction = CdoTransaction(
        transactionUid="tx-123",
        cdoTransactionStatus="ERROR",
        errorMessage="Device unreachable",
    )
    mock_password_svc = MagicMock()
    mock_password_svc.change_password.return_value = failed_transaction
    mock_password_service_class.return_value = mock_password_svc

    with pytest.raises(SystemExit):
        change_asa_local_password.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "Password change failed" in call_kwargs["msg"]


@patch("plugins.modules.change_asa_local_password.Config")
@patch("plugins.modules.change_asa_local_password.AsaUserPasswordService")
@patch("plugins.modules.change_asa_local_password.InventoryService")
@patch("plugins.modules.change_asa_local_password.AnsibleModule")
def test_should_return_structured_error_on_api_exception(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_password_service_class: MagicMock,
    _mock_config_class: MagicMock,
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

    mock_password_svc = MagicMock()
    mock_password_svc.change_password.side_effect = api_error
    mock_password_service_class.return_value = mock_password_svc

    with pytest.raises(SystemExit):
        change_asa_local_password.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert call_kwargs["msg"] == "Access denied"
    assert call_kwargs["error_code"] == "FORBIDDEN"


@patch("plugins.modules.change_asa_local_password.AnsibleModule")
def test_should_fail_if_region_not_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance_query: MagicMock,
) -> None:
    """run_module should fail when region is not provided."""
    del mock_module_instance_query.params["region"]
    mock_ansible_module_class.return_value = mock_module_instance_query

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            change_asa_local_password.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "region is required" in call_kwargs["msg"]


@patch("plugins.modules.change_asa_local_password.AnsibleModule")
def test_should_fail_if_api_token_not_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance_query: MagicMock,
) -> None:
    """run_module should fail when api_token is not provided."""
    del mock_module_instance_query.params["api_token"]
    mock_ansible_module_class.return_value = mock_module_instance_query

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            change_asa_local_password.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "api_token is required" in call_kwargs["msg"]
