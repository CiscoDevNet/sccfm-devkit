# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import sync_asa_device_config  # noqa: E402
from scc_firewall_manager_sdk import CdoTransaction, DevicePage

from ._module_contract_smoke import assert_module_contract


def test_module_contract() -> None:
    assert_module_contract("sync_asa_device_config")


def _make_transaction(
    transaction_uid: str = "txn-001",
    status: str = "PENDING",
) -> CdoTransaction:
    return CdoTransaction(transactionUid=transaction_uid, cdoTransactionStatus=status)


@pytest.fixture
def base_params() -> dict[str, Any]:
    return {
        "query": None,
        "uids": ["uid-1"],
        "limit": 50,
        "offset": 0,
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


@patch("plugins.modules.sync_asa_device_config.Config")
@patch("plugins.modules.sync_asa_device_config.InventoryService")
@patch("plugins.modules.sync_asa_device_config.AnsibleModule")
def test_should_trigger_sync_for_each_device(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params["uids"] = ["uid-1", "uid-2"]
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.read_asa_device_configuration.return_value = _make_transaction()
    mock_inv_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        sync_asa_device_config.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert kw["device_count"] == 2
    assert mock_inv.read_asa_device_configuration.call_count == 2


@patch("plugins.modules.sync_asa_device_config.Config")
@patch("plugins.modules.sync_asa_device_config.TransactionService")
@patch("plugins.modules.sync_asa_device_config.InventoryService")
@patch("plugins.modules.sync_asa_device_config.AnsibleModule")
def test_should_wait_for_completion(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params["wait"] = True
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.read_asa_device_configuration.return_value = _make_transaction(status="PENDING")
    mock_inv_cls.return_value = mock_inv

    completed = _make_transaction(status="DONE")
    mock_txn = MagicMock()
    mock_txn.wait_for_transaction_to_finish.return_value = completed
    mock_txn_cls.return_value = mock_txn

    with pytest.raises(SystemExit):
        sync_asa_device_config.run_module()

    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert kw["results"][0]["transaction"]["cdoTransactionStatus"] == "DONE"


@patch("plugins.modules.sync_asa_device_config.Config")
@patch("plugins.modules.sync_asa_device_config.TransactionService")
@patch("plugins.modules.sync_asa_device_config.InventoryService")
@patch("plugins.modules.sync_asa_device_config.AnsibleModule")
def test_should_fail_when_sync_transaction_errors(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params["wait"] = True
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.read_asa_device_configuration.return_value = _make_transaction(status="PENDING")
    mock_inv_cls.return_value = mock_inv

    failed = _make_transaction(status="ERROR")
    mock_txn = MagicMock()
    mock_txn.wait_for_transaction_to_finish.return_value = failed
    mock_txn_cls.return_value = mock_txn

    with pytest.raises(SystemExit):
        sync_asa_device_config.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "failed with status: ERROR" in kw["msg"]


@patch("plugins.modules.sync_asa_device_config.Config")
@patch("plugins.modules.sync_asa_device_config.InventoryService")
@patch("plugins.modules.sync_asa_device_config.AnsibleModule")
def test_should_fail_when_query_returns_no_devices(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params["uids"] = None
    mock_module.params["query"] = "name:nonexistent-*"
    mock_ansible_cls.return_value = mock_module

    mock_inv = MagicMock()
    mock_inv.get_devices.return_value = DevicePage(count=0, limit=50, offset=0, items=[])
    mock_inv_cls.return_value = mock_inv

    with pytest.raises(SystemExit):
        sync_asa_device_config.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "No devices found" in kw["msg"]


@patch("plugins.modules.sync_asa_device_config.Config")
@patch("plugins.modules.sync_asa_device_config.InventoryService")
@patch("plugins.modules.sync_asa_device_config.AnsibleModule")
def test_check_mode_returns_would_sync(
    mock_ansible_cls: MagicMock,
    _mock_inv_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.check_mode = True
    mock_ansible_cls.return_value = mock_module

    with pytest.raises(SystemExit):
        sync_asa_device_config.run_module()

    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert "Would sync" in kw["msg"]
