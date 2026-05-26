# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import onboard_cdfmc_ftd  # noqa: E402
from scc_firewall_manager_sdk import (
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
)


@pytest.fixture
def sample_device() -> Device:
    return Device(
        uid="cdfmc-ftd-uid-123",
        name="test-cdfmc-ftd-01",
        deviceType=EntityType.CDFMC_MANAGED_FTD,
        softwareVersion="7.4.1",
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
        cdFmcInfo={"cliKey": "test-cli-key"},
    )


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    return {
        "name": "test-cdfmc-ftd-01",
        "fmc_access_policy_uid": "policy-uid-123",
        "licenses": ["BASE"],
        "virtual": False,
        "performance_tier": None,
        "grouped_labels": {"environment": ["production"]},
        "ungrouped_labels": ["branch", "firewall"],
        "region": "us",
        "api_token": "test-token-123",
    }


@pytest.fixture
def mock_module_instance(base_module_params: dict[str, Any]) -> MagicMock:
    mock_module = MagicMock()
    mock_module.params = base_module_params.copy()
    mock_module.check_mode = False
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


@patch("plugins.modules.onboard_cdfmc_ftd.Config")
@patch("plugins.modules.onboard_cdfmc_ftd.FtdOnboardService")
@patch("plugins.modules.onboard_cdfmc_ftd.InventoryService")
@patch("plugins.modules.onboard_cdfmc_ftd.AnsibleModule")
def test_should_onboard_cdfmc_ftd_and_return_device_and_cli_key(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_ftd_onboard_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_device: Device,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(count=0, limit=1, offset=0, items=[])
    mock_inventory_service_class.return_value = mock_inventory

    mock_onboard = MagicMock()
    mock_onboard.onboard_ftd.return_value = sample_device
    mock_ftd_onboard_service_class.return_value = mock_onboard

    with pytest.raises(SystemExit):
        onboard_cdfmc_ftd.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["cli_key"] == "test-cli-key"
    assert call_kwargs["device"]["uid"] == "cdfmc-ftd-uid-123"


@patch("plugins.modules.onboard_cdfmc_ftd.Config")
@patch("plugins.modules.onboard_cdfmc_ftd.InventoryService")
@patch("plugins.modules.onboard_cdfmc_ftd.AnsibleModule")
def test_check_mode_should_return_empty_device_payload(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(count=0, limit=1, offset=0, items=[])
    mock_inventory_service_class.return_value = mock_inventory

    with pytest.raises(SystemExit):
        onboard_cdfmc_ftd.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["cli_key"] is None
    assert call_kwargs["device"] == {}
