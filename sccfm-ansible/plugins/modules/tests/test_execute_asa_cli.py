from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import execute_asa_cli  # noqa: E402
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
def sample_cli_result() -> CdoCliResult:
    """Provides a sample CLI result for testing."""
    return CdoCliResult(
        uid="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        device_uid="b2c3d4e5-f6a7-8901-bcde-f12345678901",
        execution_uid="c3d4e5f6-a7b8-9012-cdef-123456789012",
        result="ASA Version 9.16.1\nDevice Manager Version 7.16(1)",
        script="show version",
        error_msg=None,
    )


@pytest.fixture
def base_module_params_with_query() -> dict[str, Any]:
    """Provides base module parameters with query."""
    return {
        "query": "name:test-*",
        "uids": None,
        "commands": ["show version", "show running-config"],
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
        "uids": ["a1b2c3d4-e5f6-7890-abcd-ef1234567890", "b2c3d4e5-f6a7-8901-bcde-f12345678901"],
        "commands": ["show version"],
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


@patch("plugins.modules.execute_asa_cli.Config")
@patch("plugins.modules.execute_asa_cli.AsaCommandLineService")
@patch("plugins.modules.execute_asa_cli.InventoryService")
@patch("plugins.modules.execute_asa_cli.AnsibleModule")
def test_should_execute_cli_commands_with_query(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_cli_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_query: MagicMock,
    sample_device: Device,
    sample_cli_result: CdoCliResult,
) -> None:
    """run_module should execute CLI commands on devices matching query."""
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_cli = MagicMock()
    mock_cli.execute_cli.return_value = [sample_cli_result]
    mock_cli_service_class.return_value = mock_cli

    with pytest.raises(SystemExit):
        execute_asa_cli.run_module()

    mock_module_instance_query.exit_json.assert_called_once()
    call_kwargs = mock_module_instance_query.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert len(call_kwargs["results"]) == 1
    assert "Successfully executed CLI commands" in call_kwargs["msg"]


@patch("plugins.modules.execute_asa_cli.Config")
@patch("plugins.modules.execute_asa_cli.AsaCommandLineService")
@patch("plugins.modules.execute_asa_cli.InventoryService")
@patch("plugins.modules.execute_asa_cli.AnsibleModule")
def test_should_execute_cli_commands_with_uids_without_inventory_lookup(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_cli_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_uids: MagicMock,
    sample_cli_result: CdoCliResult,
) -> None:
    """run_module should execute CLI commands using UIDs directly without inventory lookup."""
    mock_ansible_module_class.return_value = mock_module_instance_uids

    mock_cli = MagicMock()
    mock_cli.execute_cli.return_value = [sample_cli_result]
    mock_cli_service_class.return_value = mock_cli

    with pytest.raises(SystemExit):
        execute_asa_cli.run_module()

    # Verify InventoryService was NOT called when UIDs are provided
    mock_inventory_service_class.assert_not_called()

    mock_module_instance_uids.exit_json.assert_called_once()
    call_kwargs = mock_module_instance_uids.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert len(call_kwargs["results"]) == 1
    # Verify the message includes the correct device count (2 UIDs provided)
    assert "2 device(s)" in call_kwargs["msg"]


@patch("plugins.modules.execute_asa_cli.Config")
@patch("plugins.modules.execute_asa_cli.InventoryService")
@patch("plugins.modules.execute_asa_cli.AnsibleModule")
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
        execute_asa_cli.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "No devices found" in call_kwargs["msg"]


@patch("plugins.modules.execute_asa_cli.Config")
@patch("plugins.modules.execute_asa_cli.AsaCommandLineService")
@patch("plugins.modules.execute_asa_cli.InventoryService")
@patch("plugins.modules.execute_asa_cli.AnsibleModule")
def test_should_fail_if_cli_execution_fails(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_cli_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_query: MagicMock,
    sample_device: Device,
) -> None:
    """run_module should fail when CLI execution raises an exception."""
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_cli = MagicMock()
    mock_cli.execute_cli.side_effect = Exception("Connection timeout")
    mock_cli_service_class.return_value = mock_cli

    with pytest.raises(SystemExit):
        execute_asa_cli.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "Connection timeout" in call_kwargs["msg"]


@patch("plugins.modules.execute_asa_cli.Config")
@patch("plugins.modules.execute_asa_cli.AsaCommandLineService")
@patch("plugins.modules.execute_asa_cli.InventoryService")
@patch("plugins.modules.execute_asa_cli.AnsibleModule")
def test_should_fail_if_transaction_returns_error(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_cli_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_query: MagicMock,
    sample_device: Device,
) -> None:
    """run_module should fail when transaction returns error status."""
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    # Return a failed transaction instead of results
    failed_transaction = CdoTransaction(
        transactionUid="e5f6a7b8-c9d0-1234-ef56-7890abcdef12",
        cdoTransactionStatus="ERROR",
        errorMessage="Device unreachable",
    )
    mock_cli = MagicMock()
    mock_cli.execute_cli.return_value = failed_transaction
    mock_cli_service_class.return_value = mock_cli

    with pytest.raises(SystemExit):
        execute_asa_cli.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "CLI execution failed" in call_kwargs["msg"]


@patch("plugins.modules.execute_asa_cli.Config")
@patch("plugins.modules.execute_asa_cli.InventoryService")
@patch("plugins.modules.execute_asa_cli.AnsibleModule")
def test_should_fail_if_inventory_lookup_raises_exception(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_query: MagicMock,
) -> None:
    """run_module should fail when inventory lookup fails."""
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.side_effect = Exception("API unavailable")
    mock_inventory_service_class.return_value = mock_inventory

    with pytest.raises(SystemExit):
        execute_asa_cli.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "API unavailable" in call_kwargs["msg"]


@patch("plugins.modules.execute_asa_cli.AnsibleModule")
def test_should_fail_if_region_not_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance_query: MagicMock,
) -> None:
    """run_module should fail when region is not provided."""
    del mock_module_instance_query.params["region"]
    mock_ansible_module_class.return_value = mock_module_instance_query

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            execute_asa_cli.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "region is required" in call_kwargs["msg"]


@patch("plugins.modules.execute_asa_cli.AnsibleModule")
def test_should_fail_if_api_token_not_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance_query: MagicMock,
) -> None:
    """run_module should fail when api_token is not provided."""
    del mock_module_instance_query.params["api_token"]
    mock_ansible_module_class.return_value = mock_module_instance_query

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            execute_asa_cli.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "api_token is required" in call_kwargs["msg"]
