# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import trigger_ftd_upgrade  # noqa: E402
from scc_firewall_manager_sdk import (
    CdoTransaction,
    ConfigState,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
    FtdVersion,
)

from cisco_sccfm_core.models.ftd_upgrade_version import FtdGroupCompatibleVersions


def _make_device(
    uid: str = "uid-1",
    software_version: str = "7.2.5",
    device_type: EntityType = EntityType.CDFMC_MANAGED_FTD,
) -> Device:
    return Device(
        uid=uid,
        name=f"ftd-{uid}",
        deviceType=device_type,
        softwareVersion=software_version,
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


def _compatible_versions(
    device_uids: list[str] | None = None,
    skipped: dict[str, str] | None = None,
) -> FtdGroupCompatibleVersions:
    v1 = FtdVersion(
        softwareVersion="7.4.1",
        upgradePackageUid="pkg-abc-123",
        upgradeType="UPGRADE",
        filename="ftd-7.4.1.pkg",
        isSuggestedVersion=True,
    )
    v2 = FtdVersion(
        softwareVersion="7.2.5",
        upgradePackageUid="pkg-def-456",
        upgradeType="UPGRADE",
        filename="ftd-7.2.5.pkg",
        isSuggestedVersion=False,
    )
    uids = device_uids or ["uid-1"]
    per_device = {uid: [v1, v2] for uid in uids}
    return FtdGroupCompatibleVersions(
        per_device=per_device,
        common_versions=[v1, v2],
        skipped=skipped or {},
    )


@pytest.fixture
def base_params() -> dict[str, Any]:
    return {
        "query": None,
        "uids": ["uid-1"],
        "limit": 50,
        "offset": 0,
        "software_version": "7.4.1",
        "stage_upgrade": False,
        "ignore_maintenance_window": False,
        "upgrade_name": None,
        "wait": False,
        "timeout": 3600,
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


# ---------- Successful upgrade ----------


@patch("plugins.modules.trigger_ftd_upgrade.create_config")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeService")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeVersionService")
@patch("plugins.modules.trigger_ftd_upgrade.InventoryService")
@patch("plugins.modules.trigger_ftd_upgrade.AnsibleModule")
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
        trigger_ftd_upgrade.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert kw["device_count"] == 1
    assert "transaction" in kw
    assert kw["skipped"] == {}


@patch("plugins.modules.trigger_ftd_upgrade.create_config")
@patch("plugins.modules.trigger_ftd_upgrade.TransactionService")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeService")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeVersionService")
@patch("plugins.modules.trigger_ftd_upgrade.InventoryService")
@patch("plugins.modules.trigger_ftd_upgrade.AnsibleModule")
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
        trigger_ftd_upgrade.run_module()

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


@patch("plugins.modules.trigger_ftd_upgrade.create_config")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeVersionService")
@patch("plugins.modules.trigger_ftd_upgrade.InventoryService")
@patch("plugins.modules.trigger_ftd_upgrade.AnsibleModule")
def test_should_be_idempotent_when_already_at_target(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_ver_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Return changed=False when device already runs the target version."""
    mock_ansible_cls.return_value = mock_module

    device = _make_device(software_version="7.4.1")
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = _compatible_versions()
    mock_ver_cls.return_value = mock_ver

    with pytest.raises(SystemExit):
        trigger_ftd_upgrade.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is False
    assert "already at" in kw["msg"]


# ---------- Skipped devices ----------


@patch("plugins.modules.trigger_ftd_upgrade.create_config")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeService")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeVersionService")
@patch("plugins.modules.trigger_ftd_upgrade.InventoryService")
@patch("plugins.modules.trigger_ftd_upgrade.AnsibleModule")
def test_should_skip_ineligible_devices_and_upgrade_rest(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_ver_cls: MagicMock,
    mock_upg_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Skip devices rejected by the API and upgrade eligible ones."""
    mock_module.params["uids"] = ["uid-1", "uid-2"]
    mock_ansible_cls.return_value = mock_module

    device1 = _make_device(uid="uid-1")
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device1)
    mock_inv_cls.return_value = mock_inv

    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = _compatible_versions(
        device_uids=["uid-1"],
        skipped={"uid-2": "Device uid-2 is not a CDFMC_MANAGED_FTD device"},
    )
    mock_ver_cls.return_value = mock_ver

    mock_upg = MagicMock()
    mock_upg.upgrade_single.return_value = SAMPLE_TRANSACTION
    mock_upg_cls.return_value = mock_upg

    with pytest.raises(SystemExit):
        trigger_ftd_upgrade.run_module()

    mock_module.warn.assert_called_once()
    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert kw["device_count"] == 1
    assert "uid-2" in kw["skipped"]


@patch("plugins.modules.trigger_ftd_upgrade.create_config")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeVersionService")
@patch("plugins.modules.trigger_ftd_upgrade.AnsibleModule")
def test_should_fail_when_all_devices_skipped(
    mock_ansible_cls: MagicMock,
    mock_ver_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Fail when all devices are rejected by the upgrade API."""
    mock_ansible_cls.return_value = mock_module

    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = FtdGroupCompatibleVersions(
        per_device={},
        common_versions=[],
        skipped={"uid-1": "Device uid-1 is not a CDFMC_MANAGED_FTD device"},
    )
    mock_ver_cls.return_value = mock_ver

    with pytest.raises(SystemExit):
        trigger_ftd_upgrade.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "No eligible devices" in kw["msg"]


# ---------- Downgrade prevention ----------


@patch("plugins.modules.trigger_ftd_upgrade.create_config")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeVersionService")
@patch("plugins.modules.trigger_ftd_upgrade.InventoryService")
@patch("plugins.modules.trigger_ftd_upgrade.AnsibleModule")
def test_should_fail_on_software_downgrade(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_ver_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Fail when software_version is lower than current."""
    mock_module.params["software_version"] = "7.0.0"
    mock_ansible_cls.return_value = mock_module

    device = _make_device(software_version="7.2.5")
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = _compatible_versions()
    mock_ver_cls.return_value = mock_ver

    with pytest.raises(SystemExit):
        trigger_ftd_upgrade.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "Downgrades are not supported" in kw["msg"]


# ---------- Incompatible version ----------


@patch("plugins.modules.trigger_ftd_upgrade.create_config")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeVersionService")
@patch("plugins.modules.trigger_ftd_upgrade.InventoryService")
@patch("plugins.modules.trigger_ftd_upgrade.AnsibleModule")
def test_should_fail_when_version_not_in_compatible_list(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_ver_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Fail when target software version is not in compatible versions."""
    mock_module.params["software_version"] = "99.99.99"
    mock_ansible_cls.return_value = mock_module

    device = _make_device()
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    mock_ver = MagicMock()
    mock_ver.get_compatible_versions.return_value = _compatible_versions()
    mock_ver_cls.return_value = mock_ver

    with pytest.raises(SystemExit):
        trigger_ftd_upgrade.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "not compatible" in kw["msg"]


# ---------- Check mode ----------


@patch("plugins.modules.trigger_ftd_upgrade.create_config")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeVersionService")
@patch("plugins.modules.trigger_ftd_upgrade.InventoryService")
@patch("plugins.modules.trigger_ftd_upgrade.AnsibleModule")
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
        trigger_ftd_upgrade.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert "Would trigger" in kw["msg"]


# ---------- Query-based resolution ----------


@patch("plugins.modules.trigger_ftd_upgrade.create_config")
@patch("plugins.modules.trigger_ftd_upgrade.InventoryService")
@patch("plugins.modules.trigger_ftd_upgrade.AnsibleModule")
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
        trigger_ftd_upgrade.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "No devices found" in kw["msg"]


# ---------- Wait failure modes ----------


@patch("plugins.modules.trigger_ftd_upgrade.create_config")
@patch("plugins.modules.trigger_ftd_upgrade.TransactionService")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeService")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeVersionService")
@patch("plugins.modules.trigger_ftd_upgrade.InventoryService")
@patch("plugins.modules.trigger_ftd_upgrade.AnsibleModule")
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
        trigger_ftd_upgrade.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "failed with status: ERROR" in kw["msg"]
    assert kw["transaction"]["errorMessage"] == "Device unreachable"


@patch("plugins.modules.trigger_ftd_upgrade.create_config")
@patch("plugins.modules.trigger_ftd_upgrade.TransactionService")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeService")
@patch("plugins.modules.trigger_ftd_upgrade.FtdUpgradeVersionService")
@patch("plugins.modules.trigger_ftd_upgrade.InventoryService")
@patch("plugins.modules.trigger_ftd_upgrade.AnsibleModule")
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
        trigger_ftd_upgrade.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "did not complete within 30 seconds" in kw["msg"]
