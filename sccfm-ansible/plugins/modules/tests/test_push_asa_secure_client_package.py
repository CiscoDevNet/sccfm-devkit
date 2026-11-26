# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from plugins.modules import push_asa_secure_client_package  # noqa: E402
from scc_firewall_manager_sdk import CdoTransaction, CompatibleSecureClientVersionDto, DevicePage

from ._module_contract_smoke import assert_module_contract


def test_module_contract() -> None:
    assert_module_contract("push_asa_secure_client_package")


def _compatible_versions() -> list[CompatibleSecureClientVersionDto]:
    return [
        CompatibleSecureClientVersionDto(version="4.10.05095", platforms=[]),
        CompatibleSecureClientVersionDto(version="5.1.15.287", platforms=[]),
    ]


def _make_transaction(
    transaction_uid: str = "txn-001",
    status: str = "PENDING",
    error_message: str | None = None,
    entity_url: str | None = None,
    transaction_polling_url: str | None = None,
) -> CdoTransaction:
    return CdoTransaction(
        transactionUid=transaction_uid,
        cdoTransactionStatus=status,
        errorMessage=error_message,
        entityUrl=entity_url,
        transactionPollingUrl=transaction_polling_url,
    )


@pytest.fixture
def base_params() -> dict[str, Any]:
    return {
        "query": None,
        "uids": ["uid-1"],
        "limit": 50,
        "offset": 0,
        "version": None,
        "platforms": None,
        "upgrade_name": None,
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


# ---------- Successful push, auto-selected version ----------


@patch("plugins.modules.push_asa_secure_client_package.Config")
@patch("plugins.modules.push_asa_secure_client_package.AsaSecureClientService")
@patch("plugins.modules.push_asa_secure_client_package.AnsibleModule")
def test_should_push_latest_version_when_not_specified(
    mock_ansible_cls: MagicMock,
    mock_svc_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_ansible_cls.return_value = mock_module

    mock_svc = MagicMock()
    mock_svc.get_compatible_versions.return_value = _compatible_versions()
    mock_svc.list_installed_packages.return_value = []
    mock_svc.push_package.return_value = _make_transaction()
    mock_svc_cls.return_value = mock_svc

    with pytest.raises(SystemExit):
        push_asa_secure_client_package.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert kw["resolved_version"] == "5.1.15.287"
    assert kw["device_count"] == 1
    mock_svc.push_package.assert_called_once()
    assert mock_svc.push_package.call_args.kwargs["version"] == "5.1.15.287"


@patch("plugins.modules.push_asa_secure_client_package.Config")
@patch("plugins.modules.push_asa_secure_client_package.AsaSecureClientService")
@patch("plugins.modules.push_asa_secure_client_package.AnsibleModule")
def test_should_push_explicit_version(
    mock_ansible_cls: MagicMock,
    mock_svc_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params["version"] = "4.10.05095"
    mock_ansible_cls.return_value = mock_module

    mock_svc = MagicMock()
    mock_svc.get_compatible_versions.return_value = _compatible_versions()
    mock_svc.list_installed_packages.return_value = []
    mock_svc.push_package.return_value = _make_transaction()
    mock_svc_cls.return_value = mock_svc

    with pytest.raises(SystemExit):
        push_asa_secure_client_package.run_module()

    kw = mock_module.exit_json.call_args[1]
    assert kw["resolved_version"] == "4.10.05095"
    assert mock_svc.push_package.call_args.kwargs["version"] == "4.10.05095"


# ---------- Idempotency ----------


@patch("plugins.modules.push_asa_secure_client_package.Config")
@patch("plugins.modules.push_asa_secure_client_package.AsaSecureClientService")
@patch("plugins.modules.push_asa_secure_client_package.AnsibleModule")
def test_should_be_idempotent_when_version_already_installed(
    mock_ansible_cls: MagicMock,
    mock_svc_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params["version"] = "5.1.15.287"
    mock_ansible_cls.return_value = mock_module

    installed_pkg = MagicMock(version="5.1.15.287")
    mock_svc = MagicMock()
    mock_svc.get_compatible_versions.return_value = _compatible_versions()
    mock_svc.list_installed_packages.return_value = [installed_pkg]
    mock_svc_cls.return_value = mock_svc

    with pytest.raises(SystemExit):
        push_asa_secure_client_package.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is False
    assert "already have" in kw["msg"]
    mock_svc.push_package.assert_not_called()


# ---------- No compatible versions ----------


@patch("plugins.modules.push_asa_secure_client_package.Config")
@patch("plugins.modules.push_asa_secure_client_package.AsaSecureClientService")
@patch("plugins.modules.push_asa_secure_client_package.AnsibleModule")
def test_should_fail_when_no_compatible_versions_and_no_version_given(
    mock_ansible_cls: MagicMock,
    mock_svc_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_ansible_cls.return_value = mock_module

    mock_svc = MagicMock()
    mock_svc.get_compatible_versions.return_value = []
    mock_svc_cls.return_value = mock_svc

    with pytest.raises(SystemExit):
        push_asa_secure_client_package.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "No compatible Secure Client versions" in kw["msg"]


# ---------- Check mode ----------


@patch("plugins.modules.push_asa_secure_client_package.Config")
@patch("plugins.modules.push_asa_secure_client_package.AsaSecureClientService")
@patch("plugins.modules.push_asa_secure_client_package.AnsibleModule")
def test_check_mode_returns_would_push(
    mock_ansible_cls: MagicMock,
    mock_svc_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.check_mode = True
    mock_ansible_cls.return_value = mock_module

    mock_svc = MagicMock()
    mock_svc.get_compatible_versions.return_value = _compatible_versions()
    mock_svc.list_installed_packages.return_value = []
    mock_svc_cls.return_value = mock_svc

    with pytest.raises(SystemExit):
        push_asa_secure_client_package.run_module()

    mock_module.exit_json.assert_called_once()
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert "Would push" in kw["msg"]
    mock_svc.push_package.assert_not_called()


# ---------- Wait mode ----------


@patch("plugins.modules.push_asa_secure_client_package.Config")
@patch("plugins.modules.push_asa_secure_client_package.TransactionService")
@patch("plugins.modules.push_asa_secure_client_package.AsaSecureClientService")
@patch("plugins.modules.push_asa_secure_client_package.AnsibleModule")
def test_should_wait_for_push_completion(
    mock_ansible_cls: MagicMock,
    mock_svc_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params["wait"] = True
    mock_module.params["timeout"] = 900
    mock_ansible_cls.return_value = mock_module

    mock_svc = MagicMock()
    mock_svc.get_compatible_versions.return_value = _compatible_versions()
    mock_svc.list_installed_packages.return_value = []
    mock_svc.push_package.return_value = _make_transaction(status="PENDING")
    mock_svc_cls.return_value = mock_svc

    completed_transaction = _make_transaction(status="DONE")
    mock_txn = MagicMock()
    mock_txn.wait_for_transaction_to_finish.return_value = completed_transaction
    mock_txn_cls.return_value = mock_txn

    with pytest.raises(SystemExit):
        push_asa_secure_client_package.run_module()

    mock_txn.wait_for_transaction_to_finish.assert_called_once_with(
        transaction_uid="txn-001",
        timeout_sec=900,
    )
    kw = mock_module.exit_json.call_args[1]
    assert kw["changed"] is True
    assert kw["transaction"]["cdoTransactionStatus"] == "DONE"


@patch("plugins.modules.push_asa_secure_client_package.Config")
@patch("plugins.modules.push_asa_secure_client_package.TransactionService")
@patch("plugins.modules.push_asa_secure_client_package.AsaSecureClientService")
@patch("plugins.modules.push_asa_secure_client_package.AnsibleModule")
def test_should_fail_when_waited_transaction_errors(
    mock_ansible_cls: MagicMock,
    mock_svc_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params["wait"] = True
    mock_ansible_cls.return_value = mock_module

    mock_svc = MagicMock()
    mock_svc.get_compatible_versions.return_value = _compatible_versions()
    mock_svc.list_installed_packages.return_value = []
    mock_svc.push_package.return_value = _make_transaction(status="PENDING")
    mock_svc_cls.return_value = mock_svc

    failed_transaction = _make_transaction(status="ERROR", error_message="Device unreachable")
    mock_txn = MagicMock()
    mock_txn.wait_for_transaction_to_finish.return_value = failed_transaction
    mock_txn_cls.return_value = mock_txn

    with pytest.raises(SystemExit):
        push_asa_secure_client_package.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "failed with status: ERROR" in kw["msg"]
    assert "Device unreachable" in kw["msg"]
    assert kw["transaction"]["errorMessage"] == "Device unreachable"


# ---------- Transaction failure detail surfacing (added 2026-11-25) ----------
# Regression test for the 2026-11-25 build #33 live failure: CDO's own
# error_message on a failed push transaction was just "FAILURE" with zero
# further detail, same opacity problem as the earlier synchronous 500s. This
# locks in that we at least surface entity_url/transaction_polling_url so the
# Jenkins log has a direct link into CDO instead of forcing a manual dig
# through the raw `transaction` dict.


@patch("plugins.modules.push_asa_secure_client_package.Config")
@patch("plugins.modules.push_asa_secure_client_package.TransactionService")
@patch("plugins.modules.push_asa_secure_client_package.AsaSecureClientService")
@patch("plugins.modules.push_asa_secure_client_package.AnsibleModule")
def test_should_surface_run_detail_urls_on_transaction_failure(
    mock_ansible_cls: MagicMock,
    mock_svc_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params["wait"] = True
    mock_ansible_cls.return_value = mock_module

    mock_svc = MagicMock()
    mock_svc.get_compatible_versions.return_value = _compatible_versions()
    mock_svc.list_installed_packages.return_value = []
    mock_svc.push_package.return_value = _make_transaction(status="PENDING")
    mock_svc_cls.return_value = mock_svc

    failed_transaction = _make_transaction(
        status="ERROR",
        error_message="FAILURE",
        entity_url="https://edge.staging.cdo.cisco.com/v1/inventory/devices/"
        "secure-client/upgrades/runs/2e711017-3e41-4321-a9f0-2b226fb7e0b1",
        transaction_polling_url="https://edge.staging.cdo.cisco.com/api/rest/"
        "v1/transactions/09e6a16c-7972-4b28-b6eb-46cfe25f278c",
    )
    mock_txn = MagicMock()
    mock_txn.wait_for_transaction_to_finish.return_value = failed_transaction
    mock_txn_cls.return_value = mock_txn

    with pytest.raises(SystemExit):
        push_asa_secure_client_package.run_module()

    kw = mock_module.fail_json.call_args[1]
    assert "FAILURE" in kw["msg"]
    assert "secure-client/upgrades/runs/2e711017" in kw["msg"]
    assert "transactions/09e6a16c" in kw["msg"]


@patch("plugins.modules.push_asa_secure_client_package.Config")
@patch("plugins.modules.push_asa_secure_client_package.TransactionService")
@patch("plugins.modules.push_asa_secure_client_package.AsaSecureClientService")
@patch("plugins.modules.push_asa_secure_client_package.AnsibleModule")
def test_should_use_fallback_text_when_no_error_detail_or_urls(
    mock_ansible_cls: MagicMock,
    mock_svc_cls: MagicMock,
    mock_txn_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_module.params["wait"] = True
    mock_ansible_cls.return_value = mock_module

    mock_svc = MagicMock()
    mock_svc.get_compatible_versions.return_value = _compatible_versions()
    mock_svc.list_installed_packages.return_value = []
    mock_svc.push_package.return_value = _make_transaction(status="PENDING")
    mock_svc_cls.return_value = mock_svc

    failed_transaction = _make_transaction(status="CANCELLED")
    mock_txn = MagicMock()
    mock_txn.wait_for_transaction_to_finish.return_value = failed_transaction
    mock_txn_cls.return_value = mock_txn

    with pytest.raises(SystemExit):
        push_asa_secure_client_package.run_module()

    kw = mock_module.fail_json.call_args[1]
    assert "no error detail returned by CDO" in kw["msg"]
    assert "Run detail:" not in kw["msg"]
    assert "Transaction:" not in kw["msg"]


# ---------- Software-version settling wait (added 2026-11-25) ----------


@patch("plugins.modules.push_asa_secure_client_package.Config")
@patch("plugins.modules.push_asa_secure_client_package.AsaSecureClientService")
@patch("plugins.modules.push_asa_secure_client_package.AnsibleModule")
def test_should_wait_for_software_version_before_resolving_target_version(
    mock_ansible_cls: MagicMock,
    mock_svc_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_ansible_cls.return_value = mock_module

    mock_svc = MagicMock()
    mock_svc.get_compatible_versions.return_value = _compatible_versions()
    mock_svc.list_installed_packages.return_value = []
    mock_svc.push_package.return_value = _make_transaction()
    mock_svc_cls.return_value = mock_svc

    with pytest.raises(SystemExit):
        push_asa_secure_client_package.run_module()

    mock_svc.wait_for_software_version.assert_called_once_with(device_uids=["uid-1"])
    # Must happen before the catalog lookup, not after.
    method_names = [call[0] for call in mock_svc.method_calls]
    assert method_names.index("wait_for_software_version") < method_names.index(
        "get_compatible_versions"
    )


@patch("plugins.modules.push_asa_secure_client_package.Config")
@patch("plugins.modules.push_asa_secure_client_package.AsaSecureClientService")
@patch("plugins.modules.push_asa_secure_client_package.AnsibleModule")
def test_should_tag_timeout_waiting_for_software_version(
    mock_ansible_cls: MagicMock,
    mock_svc_cls: MagicMock,
    _mock_cfg: MagicMock,
    mock_module: MagicMock,
) -> None:
    mock_ansible_cls.return_value = mock_module

    mock_svc = MagicMock()
    mock_svc.wait_for_software_version.side_effect = TimeoutError(
        "Device(s) ['uid-1'] did not report a software version within 300s"
    )
    mock_svc_cls.return_value = mock_svc

    with pytest.raises(SystemExit):
        push_asa_secure_client_package.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "[while waiting for device(s) to report a software version]" in kw["msg"]
    mock_svc.get_compatible_versions.assert_not_called()


# ---------- Query-based resolution ----------


@patch("plugins.modules.push_asa_secure_client_package.Config")
@patch("plugins.modules.push_asa_secure_client_package.InventoryService")
@patch("plugins.modules.push_asa_secure_client_package.AnsibleModule")
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
        push_asa_secure_client_package.run_module()

    mock_module.fail_json.assert_called_once()
    kw = mock_module.fail_json.call_args[1]
    assert "No devices found" in kw["msg"]
