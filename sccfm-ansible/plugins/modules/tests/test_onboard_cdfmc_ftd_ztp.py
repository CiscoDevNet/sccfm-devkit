from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import onboard_cdfmc_ftd_ztp  # noqa: E402
from scc_firewall_manager_sdk import Device, DevicePage, EntityType


@pytest.fixture
def sample_device() -> Device:
    return Device(
        uid="device-uid-999",
        name="branch-ftd-01",
        deviceType=EntityType.CDFMC_MANAGED_FTD,
        serial="FTD1234567890",
    )


@pytest.fixture
def base_module_params() -> dict[str, Any]:
    return {
        "name": "branch-ftd-01",
        "serial_number": "FTD1234567890",
        "licenses": ["BASE"],
        "fmc_access_policy_uid": "policy-uid-abc",
        "admin_password": None,
        "device_group_uid": None,
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


@patch("plugins.modules.onboard_cdfmc_ftd_ztp.Config")
@patch("plugins.modules.onboard_cdfmc_ftd_ztp.FtdZtpOnboardService")
@patch("plugins.modules.onboard_cdfmc_ftd_ztp.InventoryService")
@patch("plugins.modules.onboard_cdfmc_ftd_ztp.AnsibleModule")
def test_should_onboard_and_return_device_uid(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    mock_ztp_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_device: Device,
) -> None:
    mock_ansible_module_class.return_value = mock_module_instance

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(count=0, limit=1, offset=0, items=[])
    mock_inventory_service_class.return_value = mock_inventory

    mock_ztp = MagicMock()
    mock_ztp.onboard_ftd_ztp.return_value = sample_device
    mock_ztp_service_class.return_value = mock_ztp

    with pytest.raises(SystemExit):
        onboard_cdfmc_ftd_ztp.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["device_uid"] == "device-uid-999"


@patch("plugins.modules.onboard_cdfmc_ftd_ztp.Config")
@patch("plugins.modules.onboard_cdfmc_ftd_ztp.InventoryService")
@patch("plugins.modules.onboard_cdfmc_ftd_ztp.AnsibleModule")
def test_check_mode_for_new_device_returns_would_onboard(
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
        onboard_cdfmc_ftd_ztp.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["device_uid"] is None


@patch("plugins.modules.onboard_cdfmc_ftd_ztp.Config")
@patch("plugins.modules.onboard_cdfmc_ftd_ztp.InventoryService")
@patch("plugins.modules.onboard_cdfmc_ftd_ztp.AnsibleModule")
def test_idempotent_when_device_already_exists(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
    sample_device: Device,
) -> None:
    """Same name + same serial → changed=False (idempotent)."""
    mock_ansible_module_class.return_value = mock_module_instance

    existing_page = DevicePage(count=1, limit=1, offset=0, items=[sample_device])

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = existing_page
    mock_inventory_service_class.return_value = mock_inventory

    with pytest.raises(SystemExit):
        onboard_cdfmc_ftd_ztp.run_module()

    mock_module_instance.exit_json.assert_called_once()
    call_kwargs = mock_module_instance.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert call_kwargs["device_uid"] == "device-uid-999"


@patch("plugins.modules.onboard_cdfmc_ftd_ztp.Config")
@patch("plugins.modules.onboard_cdfmc_ftd_ztp.InventoryService")
@patch("plugins.modules.onboard_cdfmc_ftd_ztp.AnsibleModule")
def test_fails_when_serial_taken_under_different_name(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """Serial already onboarded under a different name → fail_json."""
    mock_ansible_module_class.return_value = mock_module_instance

    serial_device = Device(
        uid="uid-serial",
        name="old-name",
        deviceType=EntityType.CDFMC_MANAGED_FTD,
        serial="FTD1234567890",
    )

    def fake_get_devices(*, limit: int, offset: int, query: str | None = None) -> DevicePage:
        if query and 'serial:"FTD1234567890"' in query:
            return DevicePage(count=1, limit=limit, offset=offset, items=[serial_device])
        return DevicePage(count=0, limit=limit, offset=offset, items=[])

    mock_inventory = MagicMock()
    mock_inventory.get_devices.side_effect = fake_get_devices
    mock_inventory_service_class.return_value = mock_inventory

    with pytest.raises(SystemExit):
        onboard_cdfmc_ftd_ztp.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "old-name" in call_kwargs["msg"]


@patch("plugins.modules.onboard_cdfmc_ftd_ztp.Config")
@patch("plugins.modules.onboard_cdfmc_ftd_ztp.InventoryService")
@patch("plugins.modules.onboard_cdfmc_ftd_ztp.AnsibleModule")
def test_fails_when_name_taken_by_different_serial(
    mock_ansible_module_class: MagicMock,
    mock_inventory_service_class: MagicMock,
    _mock_config_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    """Name already taken by a device with a different serial → fail_json."""
    mock_ansible_module_class.return_value = mock_module_instance

    name_device = Device(
        uid="uid-other",
        name="branch-ftd-01",
        deviceType=EntityType.CDFMC_MANAGED_FTD,
        serial="DIFFERENT_SERIAL",
    )

    def fake_get_devices(*, limit: int, offset: int, query: str | None = None) -> DevicePage:
        if query and 'name:"branch-ftd-01"' in query:
            return DevicePage(count=1, limit=limit, offset=offset, items=[name_device])
        return DevicePage(count=0, limit=limit, offset=offset, items=[])

    mock_inventory = MagicMock()
    mock_inventory.get_devices.side_effect = fake_get_devices
    mock_inventory_service_class.return_value = mock_inventory

    with pytest.raises(SystemExit):
        onboard_cdfmc_ftd_ztp.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "branch-ftd-01" in call_kwargs["msg"]


@patch("plugins.modules.onboard_cdfmc_ftd_ztp.AnsibleModule")
def test_fails_when_licenses_is_empty(
    mock_ansible_module_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_module_instance.params["licenses"] = []
    mock_ansible_module_class.return_value = mock_module_instance

    with pytest.raises(SystemExit):
        onboard_cdfmc_ftd_ztp.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "license" in call_kwargs["msg"].lower()


@patch("plugins.modules.onboard_cdfmc_ftd_ztp.AnsibleModule")
def test_fails_when_invalid_license_provided(
    mock_ansible_module_class: MagicMock,
    mock_module_instance: MagicMock,
) -> None:
    mock_module_instance.params["licenses"] = ["INVALID_LICENSE"]
    mock_ansible_module_class.return_value = mock_module_instance

    with pytest.raises(SystemExit):
        onboard_cdfmc_ftd_ztp.run_module()

    mock_module_instance.fail_json.assert_called_once()
    call_kwargs = mock_module_instance.fail_json.call_args[1]
    assert "INVALID_LICENSE" in call_kwargs["msg"]
