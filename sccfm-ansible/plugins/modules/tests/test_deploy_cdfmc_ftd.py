# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import deploy_cdfmc_ftd  # noqa: E402
from scc_firewall_manager_sdk import (
    CdoTransaction,
    ConnectivityState,
    Device,
    DevicePage,
    EntityType,
)


def _make_device(uid: str = "uid-1") -> Device:
    return Device(
        uid=uid,
        name=f"ftd-{uid}",
        deviceType=EntityType.CDFMC_MANAGED_FTD,
        connectivityState=ConnectivityState.ONLINE,
    )


def _device_page(device: Device) -> DevicePage:
    return DevicePage(count=1, limit=1, offset=0, items=[device])


SAMPLE_TRANSACTION = CdoTransaction(transactionUid="txn-001")


@pytest.fixture
def base_params() -> dict[str, Any]:
    return {
        "query": None,
        "uids": ["uid-1"],
        "limit": 50,
        "offset": 0,
        "deployment_notes": None,
        "description": None,
        "ignore_warnings": False,
        "wait": False,
        "timeout": 3600,
        "profile": "default",
    }


@pytest.fixture
def mock_module(base_params: dict[str, Any]) -> MagicMock:
    m = MagicMock()
    m.params = base_params.copy()
    m.check_mode = False
    m.exit_json.side_effect = SystemExit(0)
    m.fail_json.side_effect = SystemExit(1)
    return m


# ---------- Successful deploy ----------


@patch("plugins.modules.deploy_cdfmc_ftd.Config")
@patch("plugins.modules.deploy_cdfmc_ftd.FtdDeployService")
@patch("plugins.modules.deploy_cdfmc_ftd.AnsibleModule")
def test_should_deploy_successfully(
    mock_ansible_cls: MagicMock,
    mock_deploy_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Deploy should succeed and return changed=True with transaction."""
    mock_ansible_cls.return_value = mock_module

    mock_deploy = MagicMock()
    mock_deploy.deploy_single.return_value = SAMPLE_TRANSACTION
    mock_deploy_cls.return_value = mock_deploy

    with pytest.raises(SystemExit):
        deploy_cdfmc_ftd.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert kw["device_count"] == 1
    assert "transaction" in kw


@patch("plugins.modules.deploy_cdfmc_ftd.Config")
@patch("plugins.modules.deploy_cdfmc_ftd.FtdDeployService")
@patch("plugins.modules.deploy_cdfmc_ftd.AnsibleModule")
def test_should_deploy_multiple_devices(
    mock_ansible_cls: MagicMock,
    mock_deploy_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Deploy multiple devices should use deploy_multiple."""
    mock_module.params["uids"] = ["uid-1", "uid-2"]
    mock_ansible_cls.return_value = mock_module

    mock_deploy = MagicMock()
    mock_deploy.deploy_multiple.return_value = SAMPLE_TRANSACTION
    mock_deploy_cls.return_value = mock_deploy

    with pytest.raises(SystemExit):
        deploy_cdfmc_ftd.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert kw["device_count"] == 2
    mock_deploy.deploy_multiple.assert_called_once()


@patch("plugins.modules.deploy_cdfmc_ftd.Config")
@patch("plugins.modules.deploy_cdfmc_ftd.FtdDeployService")
@patch("plugins.modules.deploy_cdfmc_ftd.AnsibleModule")
def test_should_pass_optional_params(
    mock_ansible_cls: MagicMock,
    mock_deploy_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Optional params should be passed to the service."""
    mock_module.params["deployment_notes"] = "Ticket-123"
    mock_module.params["description"] = "Policy update"
    mock_module.params["ignore_warnings"] = True
    mock_ansible_cls.return_value = mock_module

    mock_deploy = MagicMock()
    mock_deploy.deploy_single.return_value = SAMPLE_TRANSACTION
    mock_deploy_cls.return_value = mock_deploy

    with pytest.raises(SystemExit):
        deploy_cdfmc_ftd.run_module()

    mock_deploy.deploy_single.assert_called_once_with(
        device_uid="uid-1",
        deployment_notes="Ticket-123",
        description="Policy update",
        ignore_warnings=True,
    )


@patch("plugins.modules.deploy_cdfmc_ftd.Config")
@patch("plugins.modules.deploy_cdfmc_ftd.TransactionService")
@patch("plugins.modules.deploy_cdfmc_ftd.FtdDeployService")
@patch("plugins.modules.deploy_cdfmc_ftd.AnsibleModule")
def test_should_wait_for_deploy_completion(
    mock_ansible_cls: MagicMock,
    mock_deploy_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Wait mode should poll the deployment transaction and return the final transaction."""
    mock_module.params["wait"] = True
    mock_module.params["timeout"] = 900
    mock_ansible_cls.return_value = mock_module

    mock_deploy = MagicMock()
    mock_deploy.deploy_single.return_value = CdoTransaction(transactionUid="txn-001")
    mock_deploy_cls.return_value = mock_deploy

    completed_transaction = CdoTransaction(transactionUid="txn-001", cdoTransactionStatus="DONE")
    mock_txn = MagicMock()
    mock_txn.wait_for_transaction_to_finish.return_value = completed_transaction
    mock_txn_cls.return_value = mock_txn

    with pytest.raises(SystemExit):
        deploy_cdfmc_ftd.run_module()

    mock_txn.wait_for_transaction_to_finish.assert_called_once_with(
        transaction_uid="txn-001",
        timeout_sec=900,
    )
    kw = mock_module.exit_json.call_args[1]
    assert "completed" in kw["msg"]
    assert kw["transaction"]["cdoTransactionStatus"] == "DONE"


@patch("plugins.modules.deploy_cdfmc_ftd.Config")
@patch("plugins.modules.deploy_cdfmc_ftd.TransactionService")
@patch("plugins.modules.deploy_cdfmc_ftd.FtdDeployService")
@patch("plugins.modules.deploy_cdfmc_ftd.AnsibleModule")
def test_should_fail_when_waited_deploy_transaction_fails(
    mock_ansible_cls: MagicMock,
    mock_deploy_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Wait mode should fail when the deployment transaction ends in ERROR."""
    mock_module.params["wait"] = True
    mock_ansible_cls.return_value = mock_module

    mock_deploy = MagicMock()
    mock_deploy.deploy_single.return_value = CdoTransaction(transactionUid="txn-001")
    mock_deploy_cls.return_value = mock_deploy

    failed_transaction = CdoTransaction(
        transactionUid="txn-001",
        cdoTransactionStatus="ERROR",
        errorMessage="Deploy failed",
    )
    mock_txn = MagicMock()
    mock_txn.wait_for_transaction_to_finish.return_value = failed_transaction
    mock_txn_cls.return_value = mock_txn

    with pytest.raises(SystemExit):
        deploy_cdfmc_ftd.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "failed with status: ERROR" in kw["msg"]
    assert kw["transaction"]["errorMessage"] == "Deploy failed"


@patch("plugins.modules.deploy_cdfmc_ftd.Config")
@patch("plugins.modules.deploy_cdfmc_ftd.TransactionService")
@patch("plugins.modules.deploy_cdfmc_ftd.FtdDeployService")
@patch("plugins.modules.deploy_cdfmc_ftd.AnsibleModule")
def test_should_fail_when_wait_times_out(
    mock_ansible_cls: MagicMock,
    mock_deploy_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Wait mode should surface transaction timeout errors."""
    mock_module.params["wait"] = True
    mock_module.params["timeout"] = 30
    mock_ansible_cls.return_value = mock_module

    mock_deploy = MagicMock()
    mock_deploy.deploy_single.return_value = CdoTransaction(transactionUid="txn-001")
    mock_deploy_cls.return_value = mock_deploy

    mock_txn = MagicMock()
    mock_txn.wait_for_transaction_to_finish.side_effect = TimeoutError(
        "Transaction txn-001 did not complete within 30 seconds"
    )
    mock_txn_cls.return_value = mock_txn

    with pytest.raises(SystemExit):
        deploy_cdfmc_ftd.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "did not complete within 30 seconds" in kw["msg"]


# ---------- Check mode ----------


@patch("plugins.modules.deploy_cdfmc_ftd.Config")
@patch("plugins.modules.deploy_cdfmc_ftd.AnsibleModule")
def test_check_mode_returns_would_deploy(
    mock_ansible_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Check mode should report would deploy without calling the API."""
    mock_module.check_mode = True
    mock_ansible_cls.return_value = mock_module

    with pytest.raises(SystemExit):
        deploy_cdfmc_ftd.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert "Would deploy" in kw["msg"]


# ---------- Query-based resolution ----------


@patch("plugins.modules.deploy_cdfmc_ftd.Config")
@patch("plugins.modules.deploy_cdfmc_ftd.FtdDeployService")
@patch("plugins.modules.deploy_cdfmc_ftd.InventoryService")
@patch("plugins.modules.deploy_cdfmc_ftd.AnsibleModule")
def test_should_deploy_with_query(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_deploy_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    """Deploy using query should resolve UIDs and deploy."""
    mock_module.params["uids"] = None
    mock_module.params["query"] = "name:branch-*"
    mock_ansible_cls.return_value = mock_module

    device = _make_device()
    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = _device_page(device)
    mock_inv_cls.return_value = mock_inv

    mock_deploy = MagicMock()
    mock_deploy.deploy_single.return_value = SAMPLE_TRANSACTION
    mock_deploy_cls.return_value = mock_deploy

    with pytest.raises(SystemExit):
        deploy_cdfmc_ftd.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True


@patch("plugins.modules.deploy_cdfmc_ftd.Config")
@patch("plugins.modules.deploy_cdfmc_ftd.InventoryService")
@patch("plugins.modules.deploy_cdfmc_ftd.AnsibleModule")
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
        deploy_cdfmc_ftd.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "No devices found" in kw["msg"]
