# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import execute_ftd_cli
from scc_firewall_manager_sdk import (
    ApiException,
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
)

from sccfm_core.constants import CDFMC_MANAGED_FTD_DEVICE_TYPE_FILTER
from sccfm_core.models.ftd_cli_result import FtdBulkCliResult, FtdDeviceCliResponse

FMC_UID = "09590f30-8cb7-11f0-a508-8e9f8a6273f4"
SCC_UID = "d4e5f6a7-b8c9-0123-def4-567890abcdef"


@pytest.fixture
def sample_device() -> Device:
    return Device(
        uid=SCC_UID,
        name="test-ftd-01",
        deviceType=EntityType.CDFMC_MANAGED_FTD,
        deviceRecordOnFmc={"uid": FMC_UID},
        softwareVersion="7.6.0",
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def sample_result() -> FtdBulkCliResult:
    return FtdBulkCliResult(
        command="show failover",
        device_responses=[
            FtdDeviceCliResponse(
                device_uuid=FMC_UID,
                device_name="test-ftd-01",
                response="Failover Off\nFailover unit Secondary\n",
                is_error=False,
            )
        ],
    )


@pytest.fixture
def base_module_params_with_query() -> dict[str, Any]:
    return {
        "query": "name:test-*",
        "uids": None,
        "command": "show failover",
        "commands": None,
        "limit": 50,
        "offset": 0,
        "region": "us",
        "api_token": "test-token-123",
    }


@pytest.fixture
def base_module_params_with_uids() -> dict[str, Any]:
    return {
        "query": None,
        "uids": [SCC_UID],
        "command": "show version",
        "commands": None,
        "limit": 50,
        "offset": 0,
        "region": "us",
        "api_token": "test-token-123",
    }


@pytest.fixture
def mock_module_instance_query(base_module_params_with_query: dict[str, Any]) -> MagicMock:
    mock_module = MagicMock()
    mock_module.params = base_module_params_with_query.copy()
    mock_module.check_mode = False
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


@pytest.fixture
def mock_module_instance_uids(base_module_params_with_uids: dict[str, Any]) -> MagicMock:
    mock_module = MagicMock()
    mock_module.params = base_module_params_with_uids.copy()
    mock_module.check_mode = False
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


@patch("plugins.modules.execute_ftd_cli.Config")
@patch("plugins.modules.execute_ftd_cli.FtdCommandLineService")
@patch("plugins.modules.execute_ftd_cli.InventoryService")
@patch("plugins.modules.execute_ftd_cli.AnsibleModule")
def test_should_execute_cli_with_query(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_cli_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_query: MagicMock,
    sample_device: Device,
    sample_result: FtdBulkCliResult,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_cli = MagicMock()
    mock_cli.execute_cli.return_value = sample_result
    mock_cli_service_class.return_value = mock_cli

    with pytest.raises(SystemExit):
        execute_ftd_cli.run_module()

    mock_module_instance_query.exit_json.assert_called_once()
    call_kwargs = mock_module_instance_query.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["command"] == "show failover"
    assert call_kwargs["commands"] == ["show failover"]
    assert len(call_kwargs["results"]) == 1
    assert call_kwargs["results"][0]["is_error"] is False
    assert "Successfully executed" in call_kwargs["msg"]


@patch("plugins.modules.execute_ftd_cli.Config")
@patch("plugins.modules.execute_ftd_cli.FtdCommandLineService")
@patch("plugins.modules.execute_ftd_cli.InventoryService")
@patch("plugins.modules.execute_ftd_cli.AnsibleModule")
def test_should_execute_cli_with_uids(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_cli_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_uids: MagicMock,
    sample_device: Device,
    sample_result: FtdBulkCliResult,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance_uids

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_cli = MagicMock()
    mock_cli.execute_cli.return_value = sample_result
    mock_cli_service_class.return_value = mock_cli

    with pytest.raises(SystemExit):
        execute_ftd_cli.run_module()

    mock_inventory.get_devices.assert_called_once_with(
        limit=1,
        offset=0,
        query=f"(uid:{SCC_UID}) AND {CDFMC_MANAGED_FTD_DEVICE_TYPE_FILTER}",
    )
    mock_module_instance_uids.exit_json.assert_called_once()
    call_kwargs = mock_module_instance_uids.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["commands"] == ["show failover"]
    assert len(call_kwargs["results"]) == 1


@patch("plugins.modules.execute_ftd_cli.Config")
@patch("plugins.modules.execute_ftd_cli.FtdCommandLineService")
@patch("plugins.modules.execute_ftd_cli.InventoryService")
@patch("plugins.modules.execute_ftd_cli.AnsibleModule")
def test_should_accept_single_item_commands_alias(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_cli_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_query: MagicMock,
    sample_device: Device,
    sample_result: FtdBulkCliResult,
) -> None:
    mock_module_instance_query.params["command"] = None
    mock_module_instance_query.params["commands"] = ["show failover"]
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_cli = MagicMock()
    mock_cli.execute_cli.return_value = sample_result
    mock_cli_service_class.return_value = mock_cli

    with pytest.raises(SystemExit):
        execute_ftd_cli.run_module()

    mock_cli.execute_cli.assert_called_once_with(
        devices=[sample_device],
        command="show failover",
    )
    call_kwargs = mock_module_instance_query.exit_json.call_args[1]
    assert call_kwargs["command"] == "show failover"
    assert call_kwargs["commands"] == ["show failover"]


@patch("plugins.modules.execute_ftd_cli.Config")
@patch("plugins.modules.execute_ftd_cli.InventoryService")
@patch("plugins.modules.execute_ftd_cli.AnsibleModule")
def test_should_fail_when_no_devices_match(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_query: MagicMock,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(count=0, limit=50, offset=0, items=[])
    mock_inventory_service_class.return_value = mock_inventory

    with pytest.raises(SystemExit):
        execute_ftd_cli.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    assert "No devices found" in mock_module_instance_query.fail_json.call_args[1]["msg"]


@patch("plugins.modules.execute_ftd_cli.Config")
@patch("plugins.modules.execute_ftd_cli.FtdCommandLineService")
@patch("plugins.modules.execute_ftd_cli.InventoryService")
@patch("plugins.modules.execute_ftd_cli.AnsibleModule")
def test_should_fail_on_api_exception(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_cli_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_query: MagicMock,
    sample_device: Device,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_cli = MagicMock()
    mock_cli.execute_cli.side_effect = ApiException(status=500, reason="Internal Server Error")
    mock_cli_service_class.return_value = mock_cli

    with pytest.raises(SystemExit):
        execute_ftd_cli.run_module()

    mock_module_instance_query.fail_json.assert_called_once()


@patch("plugins.modules.execute_ftd_cli.AnsibleModule")
def test_should_fail_if_region_not_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance_query: MagicMock,
) -> None:
    del mock_module_instance_query.params["region"]
    mock_ansible_module_class.return_value = mock_module_instance_query

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            execute_ftd_cli.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "region is required" in call_kwargs["msg"]


@patch("plugins.modules.execute_ftd_cli.AnsibleModule")
def test_should_fail_if_api_token_not_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance_query: MagicMock,
) -> None:
    del mock_module_instance_query.params["api_token"]
    mock_ansible_module_class.return_value = mock_module_instance_query

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            execute_ftd_cli.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "api_token is required" in call_kwargs["msg"]


@patch("plugins.modules.execute_ftd_cli.Config")
@patch("plugins.modules.execute_ftd_cli.FtdCommandLineService")
@patch("plugins.modules.execute_ftd_cli.InventoryService")
@patch("plugins.modules.execute_ftd_cli.AnsibleModule")
def test_should_return_structured_error_on_api_exception(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_cli_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_query: MagicMock,
    sample_device: Device,
) -> None:
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

    mock_cli = MagicMock()
    mock_cli.execute_cli.side_effect = api_error
    mock_cli_service_class.return_value = mock_cli

    with pytest.raises(SystemExit):
        execute_ftd_cli.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert call_kwargs["msg"] == "Access denied"
    assert call_kwargs["error_code"] == "FORBIDDEN"
    assert call_kwargs["error_details"] == {"resource": "device"}
    assert call_kwargs["status_code"] == 403


@patch("plugins.modules.execute_ftd_cli.Config")
@patch("plugins.modules.execute_ftd_cli.FtdCommandLineService")
@patch("plugins.modules.execute_ftd_cli.InventoryService")
@patch("plugins.modules.execute_ftd_cli.AnsibleModule")
def test_should_support_check_mode_without_executing_cli(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_cli_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_query: MagicMock,
    sample_device: Device,
) -> None:
    mock_module_instance_query.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    with pytest.raises(SystemExit):
        execute_ftd_cli.run_module()

    mock_cli_service_class.assert_not_called()
    mock_module_instance_query.exit_json.assert_called_once()
    call_kwargs = mock_module_instance_query.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["command"] == "show failover"
    assert call_kwargs["commands"] == ["show failover"]
    assert call_kwargs["results"] == []
    assert call_kwargs["device_count"] == 1
    assert "Would execute" in call_kwargs["msg"]


@patch("plugins.modules.execute_ftd_cli.Config")
@patch("plugins.modules.execute_ftd_cli.InventoryService")
@patch("plugins.modules.execute_ftd_cli.AnsibleModule")
def test_should_fail_in_check_mode_for_invalid_command(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance_query: MagicMock,
    sample_device: Device,
) -> None:
    mock_module_instance_query.check_mode = True
    mock_module_instance_query.params["command"] = "configure network ipv4 manual"
    mock_ansible_module_class.return_value = mock_module_instance_query

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    with pytest.raises(SystemExit):
        execute_ftd_cli.run_module()

    mock_module_instance_query.fail_json.assert_called_once()
    call_kwargs = mock_module_instance_query.fail_json.call_args[1]
    assert "Only show commands are supported" in call_kwargs["msg"]
