from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import onboard_asa  # noqa: E402
from scc_firewall_manager_sdk import (
    ApiException,
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
        uid="asa-uid-123",
        name="test-asa-01",
        deviceType=EntityType.ASA,
        softwareVersion="9.16.1",
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    """Provides base module parameters."""
    return {
        "name": "test-asa-01",
        "device_address": "192.168.1.1:443",
        "username": "admin",
        "password": "secret",
        "connector_type": "CDG",
        "connector_name": None,
        "ignore_certificate": True,
        "grouped_labels": {"environment": ["production"]},
        "ungrouped_labels": ["asa", "firewall"],
        "region": "us",
        "api_token": "test-token-123",
    }


@pytest.fixture
def mock_module_instance(base_module_params: dict[str, Any]) -> MagicMock:
    """Creates a mock module instance with exit_json/fail_json that raise SystemExit."""
    mock_module = MagicMock()
    mock_module.params = base_module_params.copy()  # Copy to avoid mutation across tests
    mock_module.check_mode = False
    mock_module.exit_json.side_effect = SystemExit(0)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


@patch("plugins.modules.onboard_asa.Config")
@patch("plugins.modules.onboard_asa.AsaOnboardService")
@patch("plugins.modules.onboard_asa.InventoryService")
@patch("plugins.modules.onboard_asa.AnsibleModule")
def test_should_onboard_asa_if_device_with_name_does_not_already_exist(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_asa_onboard_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_device: Device,
) -> None:
    """run_module should onboard device when it does not already exist."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(count=0, limit=1, offset=0, items=[])
    mock_inventory_service_class.return_value = mock_inventory

    mock_onboard = MagicMock()
    mock_onboard.onboard_asa.return_value = sample_device
    mock_asa_onboard_service_class.return_value = mock_onboard

    with pytest.raises(SystemExit):
        onboard_asa.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["device"]["uid"] == "asa-uid-123"
    assert "msg" in call_kwargs


@patch("plugins.modules.onboard_asa.Config")
@patch("plugins.modules.onboard_asa.AsaOnboardService")
@patch("plugins.modules.onboard_asa.InventoryService")
@patch("plugins.modules.onboard_asa.AnsibleModule")
def test_should_return_existing_device_info_if_device_with_name_already_exists(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_asa_onboard_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_device: Device,
) -> None:
    """run_module should return existing device info without onboarding."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=1, offset=0, items=[sample_device]
    )
    mock_inventory_service_class.return_value = mock_inventory

    mock_onboard = MagicMock()
    mock_asa_onboard_service_class.return_value = mock_onboard

    with pytest.raises(SystemExit):
        onboard_asa.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["msg"] == "ASA device already exists"
    assert call_kwargs["device"]["uid"] == "asa-uid-123"
    mock_onboard.onboard_asa.assert_not_called()


@patch("plugins.modules.onboard_asa.Config")
@patch("plugins.modules.onboard_asa.AsaOnboardService")
@patch("plugins.modules.onboard_asa.InventoryService")
@patch("plugins.modules.onboard_asa.AnsibleModule")
def test_should_fail_if_asa_onboard_raises_exception(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_asa_onboard_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail with error message when onboarding fails."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(count=0, limit=1, offset=0, items=[])
    mock_inventory_service_class.return_value = mock_inventory

    mock_onboard = MagicMock()
    mock_onboard.onboard_asa.side_effect = Exception("Connection timeout")
    mock_asa_onboard_service_class.return_value = mock_onboard

    with pytest.raises(SystemExit):
        onboard_asa.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "Connection timeout" in call_kwargs["msg"]


@patch("plugins.modules.onboard_asa.Config")
@patch("plugins.modules.onboard_asa.InventoryService")
@patch("plugins.modules.onboard_asa.AnsibleModule")
def test_should_fail_if_inventory_lookup_raises_exception(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail when inventory lookup fails."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_inventory = MagicMock()
    mock_inventory.get_devices.side_effect = Exception("API unavailable")
    mock_inventory_service_class.return_value = mock_inventory

    with pytest.raises(SystemExit):
        onboard_asa.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "API unavailable" in call_kwargs["msg"]


@patch("plugins.modules.onboard_asa.AnsibleModule")
def test_should_fail_if_region_not_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail when region is not provided."""
    del mock_module_instance.params["region"]
    mock_ansible_module_class.return_value = mock_module_instance

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            onboard_asa.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "region is required" in call_kwargs["msg"]


@patch("plugins.modules.onboard_asa.AnsibleModule")
def test_should_fail_if_api_token_not_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should fail when api_token is not provided."""
    del mock_module_instance.params["api_token"]
    mock_ansible_module_class.return_value = mock_module_instance

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit):
            onboard_asa.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "api_token is required" in call_kwargs["msg"]


@patch("plugins.modules.onboard_asa.Config")
@patch("plugins.modules.onboard_asa.AsaOnboardService")
@patch("plugins.modules.onboard_asa.InventoryService")
@patch("plugins.modules.onboard_asa.AnsibleModule")
def test_should_return_structured_error_on_api_exception(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_asa_onboard_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module should return structured error info when ApiException occurs."""
    mock_ansible_module_class.return_value = mock_module_instance

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(count=0, limit=1, offset=0, items=[])
    mock_inventory_service_class.return_value = mock_inventory

    # Create ApiException with structured JSON body
    api_error = ApiException(status=400, reason="Bad Request")
    api_error.body = '{"errorMsg": "Invalid device address", "errorCode": "VALIDATION_ERROR", "details": {"field": "deviceAddress"}}'

    mock_onboard = MagicMock()
    mock_onboard.onboard_asa.side_effect = api_error
    mock_asa_onboard_service_class.return_value = mock_onboard

    with pytest.raises(SystemExit):
        onboard_asa.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert call_kwargs["msg"] == "Invalid device address"
    assert call_kwargs["error_code"] == "VALIDATION_ERROR"
    assert call_kwargs["error_details"] == {"field": "deviceAddress"}
    assert call_kwargs["status_code"] == 400


@patch("plugins.modules.onboard_asa.Config")
@patch("plugins.modules.onboard_asa.AsaOnboardService")
@patch("plugins.modules.onboard_asa.InventoryService")
@patch("plugins.modules.onboard_asa.AnsibleModule")
def test_check_mode_should_report_would_onboard_when_device_does_not_exist(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_asa_onboard_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """run_module in check_mode should report changed without onboarding."""
    mock_module_instance.check_mode = True
    mock_ansible_module_class.return_value = mock_module_instance

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(count=0, limit=1, offset=0, items=[])
    mock_inventory_service_class.return_value = mock_inventory

    mock_onboard = MagicMock()
    mock_asa_onboard_service_class.return_value = mock_onboard

    with pytest.raises(SystemExit):
        onboard_asa.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert "Would onboard" in call_kwargs["msg"]
    mock_onboard.onboard_asa.assert_not_called()
