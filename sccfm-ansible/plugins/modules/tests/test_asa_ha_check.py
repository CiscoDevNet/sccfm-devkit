"""Tests for the asa_ha_check Ansible module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import asa_ha_check  # noqa: E402
from scc_firewall_manager_sdk import (
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
)

from sccfm_core.models.asa_failover_status import (
    AsaFailoverInterface,
    AsaFailoverStatus,
    AsaFailoverUnit,
    HaCheckResult,
)
from sccfm_core.services import AsaHaCheckReport
from sccfm_core.services.inventory.asa_ha_check_service import UnmonitoredInterface

UID_1 = "11111111-1111-4111-8111-111111111111"

_HEALTHY_STATUS = AsaFailoverStatus(
    failover_enabled=True,
    failover_unit="Primary",
    lan_interface_name="INTFC",
    lan_hardware="GigabitEthernet0/8",
    lan_state="up",
    version_ours="9.20(3)10",
    version_mate="9.20(3)10",
    serial_ours="JAD251400QT",
    serial_mate="9AA77409PDA",
    last_failover="14:23:15 UTC Jun 5 2024",
    monitored_count=3,
    monitored_max=110,
    this_host=AsaFailoverUnit(
        role="Primary",
        state="Active",
        active_time=12345,
        interfaces=[
            AsaFailoverInterface(
                name="outside", ip_address="10.0.0.1", status="Normal", monitoring="Monitored"
            ),
        ],
    ),
    other_host=AsaFailoverUnit(
        role="Secondary",
        state="Standby Ready",
        active_time=0,
        interfaces=[
            AsaFailoverInterface(
                name="outside", ip_address="10.0.0.2", status="Normal", monitoring="Monitored"
            ),
        ],
    ),
    config_sync_state="Sync Done",
)


@pytest.fixture
def sample_device() -> Device:
    return Device(
        uid=UID_1,
        name="ha-asa-primary",
        deviceType=EntityType.ASA,
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


@pytest.fixture
def base_module_params_with_uids() -> dict[str, Any]:
    return {
        "query": None,
        "uids": [UID_1],
        "limit": 50,
        "offset": 0,
        "region": "us",
        "api_token": "test-token-123",
    }


@pytest.fixture
def base_module_params_with_query() -> dict[str, Any]:
    return {
        "query": "asaFailoverMode:ACTIVE_STANDBY",
        "uids": None,
        "limit": 50,
        "offset": 0,
        "region": "us",
        "api_token": "test-token-123",
    }


def _module_instance(params: dict[str, Any]) -> MagicMock:
    module = MagicMock()
    module.params = params.copy()
    module.check_mode = False
    module.exit_json.side_effect = SystemExit(0)
    module.fail_json.side_effect = SystemExit(1)
    return module


def _healthy_report() -> dict[str, AsaHaCheckReport]:
    return {
        UID_1: AsaHaCheckReport(
            failover_status=_HEALTHY_STATUS,
            checks=[
                HaCheckResult(name="failover_enabled", passed=True, detail="Failover is ON"),
                HaCheckResult(name="lan_link", passed=True, detail="LAN link is up"),
                HaCheckResult(
                    name="version_match", passed=True, detail="Both units running 9.20(3)10"
                ),
                HaCheckResult(name="mate_ready", passed=True, detail="Mate is Standby Ready"),
                HaCheckResult(
                    name="interfaces_healthy",
                    passed=True,
                    detail="All 3 monitored interfaces Normal",
                ),
                HaCheckResult(
                    name="config_synced", passed=True, detail="Configuration sync completed"
                ),
                HaCheckResult(name="unmonitored_interfaces", passed=True, detail="All monitored"),
            ],
            unmonitored_interfaces=[],
        ),
    }


def _failing_report() -> dict[str, AsaHaCheckReport]:
    return {
        UID_1: AsaHaCheckReport(
            failover_status=_HEALTHY_STATUS,
            checks=[
                HaCheckResult(name="failover_enabled", passed=True, detail="Failover is ON"),
                HaCheckResult(name="lan_link", passed=True, detail="LAN link is up"),
                HaCheckResult(name="version_match", passed=False, detail="Version mismatch"),
                HaCheckResult(name="mate_ready", passed=True, detail="Mate is Standby Ready"),
                HaCheckResult(name="interfaces_healthy", passed=True, detail="All Normal"),
                HaCheckResult(name="config_synced", passed=True, detail="Sync Done"),
                HaCheckResult(
                    name="unmonitored_interfaces", passed=False, detail="dmz not monitored"
                ),
            ],
            unmonitored_interfaces=[
                UnmonitoredInterface(hardware_name="GigabitEthernet0/3", name="dmz"),
            ],
        ),
    }


@patch("plugins.modules.asa_ha_check.AsaHaCheckService")
@patch("plugins.modules.asa_ha_check.AnsibleModule")
def test_should_return_healthy_results_with_uids(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    base_module_params_with_uids: dict[str, Any],
) -> None:
    mock_module = _module_instance(base_module_params_with_uids)
    mock_ansible_module_class.return_value = mock_module

    mock_service = MagicMock()
    mock_service.check_ha.return_value = _healthy_report()
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        asa_ha_check.run_module()

    mock_module.exit_json.assert_called_once()
    kwargs = mock_module.exit_json.call_args.kwargs
    assert kwargs["changed"] is False
    assert kwargs["all_passed"] is True
    assert len(kwargs["results"]) == 1
    assert kwargs["results"][0]["device_uid"] == UID_1
    assert kwargs["results"][0]["all_passed"] is True
    assert len(kwargs["results"][0]["checks"]) == 7


@patch("plugins.modules.asa_ha_check.AsaHaCheckService")
@patch("plugins.modules.asa_ha_check.InventoryService")
@patch("plugins.modules.asa_ha_check.AnsibleModule")
def test_should_resolve_devices_from_query(
    mock_ansible_module_class: MagicMock,
    mock_inventory_class: MagicMock,
    mock_service_class: MagicMock,
    base_module_params_with_query: dict[str, Any],
    sample_device: Device,
) -> None:
    mock_module = _module_instance(base_module_params_with_query)
    mock_ansible_module_class.return_value = mock_module

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(
        count=1, limit=50, offset=0, items=[sample_device]
    )
    mock_inventory_class.return_value = mock_inventory

    mock_service = MagicMock()
    mock_service.check_ha.return_value = _healthy_report()
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        asa_ha_check.run_module()

    mock_module.exit_json.assert_called_once()
    mock_inventory.get_devices.assert_called_once()
    call_kwargs = mock_inventory.get_devices.call_args.kwargs
    assert "deviceType:ASA" in call_kwargs["query"]


@patch("plugins.modules.asa_ha_check.AsaHaCheckService")
@patch("plugins.modules.asa_ha_check.AnsibleModule")
def test_should_report_failures(
    mock_ansible_module_class: MagicMock,
    mock_service_class: MagicMock,
    base_module_params_with_uids: dict[str, Any],
) -> None:
    mock_module = _module_instance(base_module_params_with_uids)
    mock_ansible_module_class.return_value = mock_module

    mock_service = MagicMock()
    mock_service.check_ha.return_value = _failing_report()
    mock_service_class.return_value = mock_service

    with pytest.raises(SystemExit):
        asa_ha_check.run_module()

    mock_module.exit_json.assert_called_once()
    kwargs = mock_module.exit_json.call_args.kwargs
    assert kwargs["all_passed"] is False
    report = kwargs["results"][0]
    assert report["all_passed"] is False
    failed_checks = [c for c in report["checks"] if not c["passed"]]
    assert len(failed_checks) == 2
    assert report["unmonitored_interfaces"][0]["name"] == "dmz"


@patch("plugins.modules.asa_ha_check.InventoryService")
@patch("plugins.modules.asa_ha_check.AnsibleModule")
def test_should_fail_when_no_devices_found(
    mock_ansible_module_class: MagicMock,
    mock_inventory_class: MagicMock,
    base_module_params_with_query: dict[str, Any],
) -> None:
    mock_module = _module_instance(base_module_params_with_query)
    mock_ansible_module_class.return_value = mock_module

    mock_inventory = MagicMock()
    mock_inventory.get_devices.return_value = DevicePage(count=0, limit=50, offset=0, items=[])
    mock_inventory_class.return_value = mock_inventory

    with pytest.raises(SystemExit):
        asa_ha_check.run_module()

    mock_module.fail_json.assert_called_once()
    assert "No devices found" in mock_module.fail_json.call_args.kwargs["msg"]
