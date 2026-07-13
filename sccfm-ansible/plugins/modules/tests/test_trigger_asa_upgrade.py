# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import trigger_asa_upgrade  # noqa: E402
from scc_firewall_manager_sdk import (
    AsaCompatibleVersion,
    CdoTransaction,
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
)

from cisco_sccfm_core.models.asa_upgrade_version import AsaGroupCompatibleVersions


def _make_device(
    uid: str = "uid-1",
    software_version: str = "9.16(1)",
    asdm_version: str = "7.16(1)",
) -> Device:
    return Device(
        uid=uid,
        name=f"asa-{uid}",
        deviceType=EntityType.ASA,
        softwareVersion=software_version,
        asdmVersion=asdm_version,
        connectivityState=ConnectivityState.ONLINE,
        configState=ConfigState.SYNCED,
    )


def _device_page(device: Device) -> DevicePage:
    return DevicePage(count=1, limit=1, offset=0, items=[device])


SAMPLE_TRANSACTION = CdoTransaction(
    transactionUid="txn-001",
)


def _make_transaction(
    transaction_uid: str = "txn-001",
    status: str = "PENDING",
    error_message: str | None = None,
) -> CdoTransaction:
    return CdoTransaction(
        transactionUid=transaction_uid,
        cdoTransactionStatus=status,
        errorMessage=error_message,
    )


@pytest.fixture
def base_params() -> dict[str, Any]:
    return {
        "query": None,
        "uids": ["uid-1"],
        "limit": 50,
        "offset": 0,
        "software_version": "9.18(4)",
        "asdm_version": "7.18(1.152)",
        "stage_upgrade": False,
        "force_upgrade": False,
        "ignore_maintenance_window": False,
        "upgrade_name": None,
        "region": "us",
        "api_token": "test-token",
    }


@pytest.fixture
def mock_module(base_params: dict[str, Any]) -> MagicMock:
    m = MagicMock()
    m.params = base_params.copy()
    m.check_mode = False
    m.exit_json.side_effect = SystemExit(0)
    m.fail_json.side_effect = SystemExit(1)
    return m


def _compatible_versions() -> AsaGroupCompatibleVersions:
    versions = [
        AsaCompatibleVersion(softwareVersion="9.18(4)", asdmVersion="7.18(1.152)"),
        AsaCompatibleVersion(softwareVersion="9.18(4)", asdmVersion="7.16(1)"),
        AsaCompatibleVersion(softwareVersion="9.16(1)", asdmVersion="7.16(1)"),
    ]
    return AsaGroupCompatibleVersions(
        per_device={"uid-1": versions},
        common_versions=versions,
    )


# ---------- Successful upgrade ----------


@patch("plugins.modules.trigger_asa_upgrade.Config")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeService")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeVersionService")
@patch("plugins.modules.trigger_asa_upgrade.InventoryService")
@patch("plugins.modules.trigger_asa_upgrade.AnsibleModule")
def test_should_trigger_upgrade(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_ver_cls: MagicMock,
    mock_upg_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Trigger upgrade when device is not at target version."""
    mock_ansible_cls.return_value = mock_module

    device = _make_device()
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = _compatible_versions()
    mock_ver_cls.return_value = mock_ver

    mock_upg = MagicMock()
    mock_upg.upgrade_single.return_value = SAMPLE_TRANSACTION
    mock_upg_cls.return_value = mock_upg

    with pytest.raises(SystemExit):
        trigger_asa_upgrade.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert kw["device_count"] == 1
    assert "transaction" in kw


@patch("plugins.modules.trigger_asa_upgrade.Config")
@patch("plugins.modules.trigger_asa_upgrade.TransactionService")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeService")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeVersionService")
@patch("plugins.modules.trigger_asa_upgrade.InventoryService")
@patch("plugins.modules.trigger_asa_upgrade.AnsibleModule")
def test_should_wait_for_upgrade_completion(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_ver_cls: MagicMock,
    mock_upg_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Wait mode should return the final completed transaction."""
    mock_module.params["wait"] = True
    mock_module.params["timeout"] = 900
    mock_ansible_cls.return_value = mock_module

    device = _make_device()
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = _compatible_versions()
    mock_ver_cls.return_value = mock_ver

    mock_upg = MagicMock()
    mock_upg.upgrade_single.return_value = _make_transaction(status="PENDING")
    mock_upg_cls.return_value = mock_upg

    completed_transaction = _make_transaction(status="DONE")
    mock_txn = MagicMock()
    mock_txn.wait_for_transaction_to_finish.return_value = completed_transaction
    mock_txn_cls.return_value = mock_txn

    with pytest.raises(SystemExit):
        trigger_asa_upgrade.run_module()

    mock_txn.wait_for_transaction_to_finish.assert_called_once_with(
        transaction_uid="txn-001",
        timeout_sec=900,
    )
    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert "completed" in kw["msg"]
    assert kw["transaction"]["cdoTransactionStatus"] == "DONE"


# ---------- Idempotency ----------


@patch("plugins.modules.trigger_asa_upgrade.Config")
@patch("plugins.modules.trigger_asa_upgrade.InventoryService")
@patch("plugins.modules.trigger_asa_upgrade.AnsibleModule")
def test_should_be_idempotent_when_already_at_target(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Return changed=False when device already runs the target version(s)."""
    mock_ansible_cls.return_value = mock_module

    device = _make_device(software_version="9.18(4)", asdm_version="7.18(1.152)")
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        trigger_asa_upgrade.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is False
    assert "already at" in kw["msg"]


@patch("plugins.modules.trigger_asa_upgrade.Config")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeService")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeVersionService")
@patch("plugins.modules.trigger_asa_upgrade.InventoryService")
@patch("plugins.modules.trigger_asa_upgrade.AnsibleModule")
def test_should_not_be_idempotent_when_sw_differs(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_ver_cls: MagicMock,
    mock_upg_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Proceed with upgrade when software version differs."""
    mock_module.params["asdm_version"] = None
    mock_ansible_cls.return_value = mock_module

    device = _make_device(software_version="9.16(1)")
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = _compatible_versions()
    mock_ver_cls.return_value = mock_ver

    mock_upg = MagicMock()
    mock_upg.upgrade_single.return_value = SAMPLE_TRANSACTION
    mock_upg_cls.return_value = mock_upg

    with pytest.raises(SystemExit):
        trigger_asa_upgrade.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True


# ---------- Downgrade prevention ----------


@patch("plugins.modules.trigger_asa_upgrade.Config")
@patch("plugins.modules.trigger_asa_upgrade.InventoryService")
@patch("plugins.modules.trigger_asa_upgrade.AnsibleModule")
def test_should_fail_on_software_downgrade(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Fail when software_version is lower than current."""
    mock_module.params["software_version"] = "9.14(1)"
    mock_module.params["asdm_version"] = None
    mock_ansible_cls.return_value = mock_module

    device = _make_device(software_version="9.16(1)")
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        trigger_asa_upgrade.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "Downgrades are not supported" in kw["msg"]


@patch("plugins.modules.trigger_asa_upgrade.Config")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeService")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeVersionService")
@patch("plugins.modules.trigger_asa_upgrade.InventoryService")
@patch("plugins.modules.trigger_asa_upgrade.AnsibleModule")
def test_should_allow_asdm_downgrade(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_ver_cls: MagicMock,
    mock_upg_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """ASDM downgrade should be allowed."""
    mock_module.params["software_version"] = None
    mock_module.params["asdm_version"] = "7.10(1)"
    mock_ansible_cls.return_value = mock_module

    device = _make_device(asdm_version="7.16(1)")
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    compat_versions = AsaGroupCompatibleVersions(
        per_device={
            "uid-1": [
                AsaCompatibleVersion(softwareVersion="9.16(1)", asdmVersion="7.10(1)"),
            ]
        },
        common_versions=[
            AsaCompatibleVersion(softwareVersion="9.16(1)", asdmVersion="7.10(1)"),
        ],
    )
    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = compat_versions
    mock_ver_cls.return_value = mock_ver

    mock_upg = MagicMock()
    mock_upg.upgrade_single.return_value = SAMPLE_TRANSACTION
    mock_upg_cls.return_value = mock_upg

    with pytest.raises(SystemExit):
        trigger_asa_upgrade.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True


# ---------- Version required ----------


@patch("plugins.modules.trigger_asa_upgrade.Config")
@patch("plugins.modules.trigger_asa_upgrade.AnsibleModule")
def test_should_fail_when_no_version_given(
    mock_ansible_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Fail when neither software_version nor asdm_version is provided."""
    mock_module.params["software_version"] = None
    mock_module.params["asdm_version"] = None
    mock_ansible_cls.return_value = mock_module

    with pytest.raises(SystemExit):
        trigger_asa_upgrade.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "At least one" in kw["msg"]


# ---------- ASDM compatibility ----------


@patch("plugins.modules.trigger_asa_upgrade.Config")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeVersionService")
@patch("plugins.modules.trigger_asa_upgrade.InventoryService")
@patch("plugins.modules.trigger_asa_upgrade.AnsibleModule")
def test_should_fail_on_incompatible_asdm_version(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_ver_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Fail when ASDM version is not compatible with the target SW version."""
    mock_module.params["software_version"] = "9.18(4)"
    mock_module.params["asdm_version"] = "7.20(1)"  # higher than current but not in compatible set
    mock_ansible_cls.return_value = mock_module

    device = _make_device(software_version="9.16(1)", asdm_version="7.16(1)")
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = _compatible_versions()
    mock_ver_cls.return_value = mock_ver

    with pytest.raises(SystemExit):
        trigger_asa_upgrade.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "not compatible" in kw["msg"]


@patch("plugins.modules.trigger_asa_upgrade.Config")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeVersionService")
@patch("plugins.modules.trigger_asa_upgrade.InventoryService")
@patch("plugins.modules.trigger_asa_upgrade.AnsibleModule")
def test_should_fail_when_sw_version_not_in_compatible_list(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_ver_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Fail when target software version is not in compatible versions."""
    mock_module.params["software_version"] = "99.99(99)"
    mock_module.params["asdm_version"] = None
    mock_ansible_cls.return_value = mock_module

    device = _make_device()
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = _compatible_versions()
    mock_ver_cls.return_value = mock_ver

    with pytest.raises(SystemExit):
        trigger_asa_upgrade.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "not compatible" in kw["msg"]


# ---------- Check mode ----------


@patch("plugins.modules.trigger_asa_upgrade.Config")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeVersionService")
@patch("plugins.modules.trigger_asa_upgrade.InventoryService")
@patch("plugins.modules.trigger_asa_upgrade.AnsibleModule")
def test_check_mode_returns_would_trigger(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_ver_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Check mode should report would trigger without calling the API."""
    mock_module.check_mode = True
    mock_ansible_cls.return_value = mock_module

    device = _make_device()
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = _compatible_versions()
    mock_ver_cls.return_value = mock_ver

    with pytest.raises(SystemExit):
        trigger_asa_upgrade.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert "Would trigger" in kw["msg"]


# ---------- Query-based resolution ----------


@patch("plugins.modules.trigger_asa_upgrade.Config")
@patch("plugins.modules.trigger_asa_upgrade.InventoryService")
@patch("plugins.modules.trigger_asa_upgrade.AnsibleModule")
def test_should_fail_when_query_returns_no_devices(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Fail when no devices match the query."""
    mock_module.params["uids"] = None
    mock_module.params["query"] = "name:nonexistent-*"
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=0, limit=50, offset=0, items=[])
    mock_inv_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        trigger_asa_upgrade.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "No devices found" in kw["msg"]


@patch("plugins.modules.trigger_asa_upgrade.Config")
@patch("plugins.modules.trigger_asa_upgrade.TransactionService")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeService")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeVersionService")
@patch("plugins.modules.trigger_asa_upgrade.InventoryService")
@patch("plugins.modules.trigger_asa_upgrade.AnsibleModule")
def test_should_fail_when_waited_transaction_errors(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_ver_cls: MagicMock,
    mock_upg_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Wait mode should fail when the transaction ends in ERROR."""
    mock_module.params["wait"] = True
    mock_ansible_cls.return_value = mock_module

    device = _make_device()
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = _compatible_versions()
    mock_ver_cls.return_value = mock_ver

    mock_upg = MagicMock()
    mock_upg.upgrade_single.return_value = _make_transaction(status="PENDING")
    mock_upg_cls.return_value = mock_upg

    failed_transaction = _make_transaction(status="ERROR", error_message="Device unreachable")
    mock_txn = MagicMock()
    mock_txn.wait_for_transaction_to_finish.return_value = failed_transaction
    mock_txn_cls.return_value = mock_txn

    with pytest.raises(SystemExit):
        trigger_asa_upgrade.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "failed with status: ERROR" in kw["msg"]
    assert kw["transaction"]["errorMessage"] == "Device unreachable"


@patch("plugins.modules.trigger_asa_upgrade.Config")
@patch("plugins.modules.trigger_asa_upgrade.TransactionService")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeService")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeVersionService")
@patch("plugins.modules.trigger_asa_upgrade.InventoryService")
@patch("plugins.modules.trigger_asa_upgrade.AnsibleModule")
def test_should_fail_when_waited_transaction_is_cancelled(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_ver_cls: MagicMock,
    mock_upg_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Wait mode should fail when the transaction ends in CANCELLED."""
    mock_module.params["wait"] = True
    mock_ansible_cls.return_value = mock_module

    device = _make_device()
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = _compatible_versions()
    mock_ver_cls.return_value = mock_ver

    mock_upg = MagicMock()
    mock_upg.upgrade_single.return_value = _make_transaction(status="PENDING")
    mock_upg_cls.return_value = mock_upg

    cancelled_transaction = _make_transaction(status="CANCELLED")
    mock_txn = MagicMock()
    mock_txn.wait_for_transaction_to_finish.return_value = cancelled_transaction
    mock_txn_cls.return_value = mock_txn

    with pytest.raises(SystemExit):
        trigger_asa_upgrade.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "failed with status: CANCELLED" in kw["msg"]


@patch("plugins.modules.trigger_asa_upgrade.Config")
@patch("plugins.modules.trigger_asa_upgrade.TransactionService")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeService")
@patch("plugins.modules.trigger_asa_upgrade.AsaUpgradeVersionService")
@patch("plugins.modules.trigger_asa_upgrade.InventoryService")
@patch("plugins.modules.trigger_asa_upgrade.AnsibleModule")
def test_should_fail_when_wait_times_out(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_ver_cls: MagicMock,
    mock_upg_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Wait mode should surface transaction timeout errors."""
    mock_module.params["wait"] = True
    mock_module.params["timeout"] = 30
    mock_ansible_cls.return_value = mock_module

    device = _make_device()
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = _compatible_versions()
    mock_ver_cls.return_value = mock_ver

    mock_upg = MagicMock()
    mock_upg.upgrade_single.return_value = _make_transaction(status="PENDING")
    mock_upg_cls.return_value = mock_upg

    mock_txn = MagicMock()
    mock_txn.wait_for_transaction_to_finish.side_effect = TimeoutError(
        "Transaction txn-001 did not complete within 30 seconds"
    )
    mock_txn_cls.return_value = mock_txn

    with pytest.raises(SystemExit):
        trigger_asa_upgrade.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "did not complete within 30 seconds" in kw["msg"]
