# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from unittest.mock import Mock

from scc_firewall_manager_sdk import CdoTransaction, ConnectivityState, Device, FtdRegistrationInput

from sccfm_core.constants import ONBOARD_POLLING_INTERVAL_SEC
from sccfm_core.services.inventory.ftd_register_service import FtdRegisterService


def test_register_ftd_waits_for_transaction_and_polls_until_online(monkeypatch: object) -> None:
    service = FtdRegisterService.__new__(FtdRegisterService)
    service.inventory_api = Mock()
    service.transaction_service = Mock()

    pending_device = Device(uid="device-1", name="ftd-1", deviceType="CDFMC_MANAGED_FTD")
    online_device = Device(
        uid="device-1",
        name="ftd-1",
        deviceType="CDFMC_MANAGED_FTD",
        connectivityState=ConnectivityState.ONLINE,
    )
    service.inventory_api.finish_onboarding_ftd_device.return_value = CdoTransaction(
        transactionUid="txn-1"
    )
    service.transaction_service.wait_for_transaction_to_finish.return_value = CdoTransaction(
        transactionUid="txn-1",
        cdoTransactionStatus="DONE",
        entityUid="device-1",
    )
    service.inventory_api.get_device.side_effect = [pending_device, online_device]

    import sccfm_core.services.inventory.ftd_register_service as svc_module

    monkeypatch.setattr(svc_module.time, "sleep", lambda _: None)  # type: ignore[attr-defined]

    result = service.register_ftd(ftd_uid="device-1")

    assert result is online_device
    assert service.inventory_api.get_device.call_count == 2
    service.transaction_service.wait_for_transaction_to_finish.assert_called_once_with(
        transaction_uid="txn-1",
        polling_interval_sec=ONBOARD_POLLING_INTERVAL_SEC,
    )


def test_register_ftd_raises_on_failed_transaction() -> None:
    service = FtdRegisterService.__new__(FtdRegisterService)
    service.inventory_api = Mock()
    service.transaction_service = Mock()

    service.inventory_api.finish_onboarding_ftd_device.return_value = CdoTransaction(
        transactionUid="txn-2"
    )
    service.transaction_service.wait_for_transaction_to_finish.return_value = CdoTransaction(
        transactionUid="txn-2",
        cdoTransactionStatus="ERROR",
        entityUid="device-2",
    )

    try:
        service.register_ftd(ftd_uid="device-2")
        assert False, "Expected exception was not raised"
    except Exception as e:
        assert "ERROR" in str(e)
