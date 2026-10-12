# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import read_asa_config  # noqa: E402
from scc_firewall_manager_sdk import CdoTransaction, Device, DevicePage, EntityType


def _make_transaction(status: str = "PENDING") -> CdoTransaction:
    return CdoTransaction(transactionUid="txn-001", cdoTransactionStatus=status)


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


@patch("plugins.modules.read_asa_config.Config")
@patch("plugins.modules.read_asa_config.AsaConfigReadService")
@patch("plugins.modules.read_asa_config.AnsibleModule")
def test_should_start_read_for_given_uids(
    mock_ansible_cls: MagicMock,
    mock_read_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_ansible_cls.return_value = mock_module
    mock_read_cls.return_value.read_configuration.return_value = _make_transaction()

    with pytest.raises(SystemExit):
        read_asa_config.run_module()

    mock_read_cls.return_value.read_configuration.assert_called_once_with(device_uids=["uid-1"])
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert kw["device_count"] == 1
    assert "started" in kw["msg"]
    assert kw["transaction"]["transactionUid"] == "txn-001"


@patch("plugins.modules.read_asa_config.Config")
@patch("plugins.modules.read_asa_config.AsaConfigReadService")
@patch("plugins.modules.read_asa_config.InventoryService")
@patch("plugins.modules.read_asa_config.AnsibleModule")
def test_should_resolve_devices_from_query(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_read_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params.update({"uids": None, "query": "name:branch-*"})
    mock_ansible_cls.return_value = mock_module
    devices = [Device(uid=f"uid-{i}", name=f"asa-{i}", deviceType=EntityType.ASA) for i in (1, 2)]
    mock_inv_cls.return_value.get_devices.return_value = DevicePage(count=2, items=devices)
    mock_read_cls.return_value.read_configuration.return_value = _make_transaction()

    with pytest.raises(SystemExit):
        read_asa_config.run_module()

    query = mock_inv_cls.return_value.get_devices.call_args.kwargs["query"]
    assert query.startswith("(name:branch-*) AND ")
    mock_read_cls.return_value.read_configuration.assert_called_once_with(
        device_uids=["uid-1", "uid-2"]
    )


@patch("plugins.modules.read_asa_config.Config")
@patch("plugins.modules.read_asa_config.TransactionService")
@patch("plugins.modules.read_asa_config.AsaConfigReadService")
@patch("plugins.modules.read_asa_config.AnsibleModule")
def test_should_wait_for_read_completion(
    mock_ansible_cls: MagicMock,
    mock_read_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params.update({"wait": True, "timeout": 120})
    mock_ansible_cls.return_value = mock_module
    mock_read_cls.return_value.read_configuration.return_value = _make_transaction()
    mock_txn_cls.return_value.wait_for_transaction_to_finish.return_value = _make_transaction(
        "DONE"
    )

    with pytest.raises(SystemExit):
        read_asa_config.run_module()

    mock_txn_cls.return_value.wait_for_transaction_to_finish.assert_called_once_with(
        transaction_uid="txn-001", timeout_sec=120
    )
    kw = mock_module.exit_json.call_args[1]
    assert "completed" in kw["msg"]
    assert kw["transaction"]["cdoTransactionStatus"] == "DONE"


@pytest.mark.parametrize("final_status", ["ERROR", "CANCELLED"])
@patch("plugins.modules.read_asa_config.Config")
@patch("plugins.modules.read_asa_config.TransactionService")
@patch("plugins.modules.read_asa_config.AsaConfigReadService")
@patch("plugins.modules.read_asa_config.AnsibleModule")
def test_should_fail_when_waited_read_does_not_finish(
    mock_ansible_cls: MagicMock,
    mock_read_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    final_status: str,
    mock_module: MagicMock,
) -> None:
    mock_module.params["wait"] = True
    mock_ansible_cls.return_value = mock_module
    mock_read_cls.return_value.read_configuration.return_value = _make_transaction()
    mock_txn_cls.return_value.wait_for_transaction_to_finish.return_value = _make_transaction(
        final_status
    )

    with pytest.raises(SystemExit):
        read_asa_config.run_module()

    mock_module.exit_json.assert_not_called()
    kw = mock_module.fail_json.call_args[1]
    assert final_status in kw["msg"]
    assert kw["transaction"]["cdoTransactionStatus"] == final_status


@patch("plugins.modules.read_asa_config.Config")
@patch("plugins.modules.read_asa_config.TransactionService")
@patch("plugins.modules.read_asa_config.AsaConfigReadService")
@patch("plugins.modules.read_asa_config.AnsibleModule")
def test_should_fail_when_wait_times_out(
    mock_ansible_cls: MagicMock,
    mock_read_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params["wait"] = True
    mock_ansible_cls.return_value = mock_module
    mock_read_cls.return_value.read_configuration.return_value = _make_transaction()
    mock_txn_cls.return_value.wait_for_transaction_to_finish.side_effect = TimeoutError(
        "Transaction txn-001 did not complete within 3600 seconds"
    )

    with pytest.raises(SystemExit):
        read_asa_config.run_module()

    assert "did not complete" in mock_module.fail_json.call_args[1]["msg"]


@patch("plugins.modules.read_asa_config.Config")
@patch("plugins.modules.read_asa_config.AsaConfigReadService")
@patch("plugins.modules.read_asa_config.AnsibleModule")
def test_check_mode_returns_would_read_without_reading(
    mock_ansible_cls: MagicMock,
    mock_read_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.check_mode = True
    mock_ansible_cls.return_value = mock_module

    with pytest.raises(SystemExit):
        read_asa_config.run_module()

    mock_read_cls.return_value.read_configuration.assert_not_called()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert "Would read" in kw["msg"]


@patch("plugins.modules.read_asa_config.Config")
@patch("plugins.modules.read_asa_config.AsaConfigReadService")
@patch("plugins.modules.read_asa_config.InventoryService")
@patch("plugins.modules.read_asa_config.AnsibleModule")
def test_should_fail_when_query_returns_no_devices(
    mock_ansible_cls: MagicMock,
    mock_inv_cls: MagicMock,
    mock_read_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params.update({"uids": None, "query": "name:missing-*"})
    mock_ansible_cls.return_value = mock_module
    mock_inv_cls.return_value.get_devices.return_value = DevicePage(count=0, items=[])

    with pytest.raises(SystemExit):
        read_asa_config.run_module()

    mock_read_cls.return_value.read_configuration.assert_not_called()
    assert "No devices found" in mock_module.fail_json.call_args[1]["msg"]
