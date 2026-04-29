from __future__ import annotations

from typing import cast
from unittest.mock import Mock

from scc_firewall_manager_sdk import CdoTransaction, Device, FtdCreateOrUpdateInput

from sccfm_core.constants import ONBOARD_POLLING_INTERVAL_SEC
from sccfm_core.services.inventory.ftd_onboard_service import FtdOnboardService


def test_onboard_ftd_waits_for_transaction_and_fetches_device() -> None:
    service = FtdOnboardService.__new__(FtdOnboardService)
    service.inventory_api = Mock()
    service.transaction_service = Mock()

    expected_device = Device(
        uid="device-1",
        name="ftd-1",
        deviceType="CDFMC_MANAGED_FTD",
    )
    service.inventory_api.create_ftd_device.return_value = CdoTransaction(transactionUid="txn-1")
    service.transaction_service.wait_for_transaction_to_finish.return_value = CdoTransaction(
        transactionUid="txn-1",
        cdoTransactionStatus="DONE",
        entityUid="device-1",
    )
    service.inventory_api.get_device.return_value = expected_device

    result = service.onboard_ftd(cast(FtdCreateOrUpdateInput, Mock()))

    assert result is expected_device
    service.transaction_service.wait_for_transaction_to_finish.assert_called_once_with(
        transaction_uid="txn-1",
        polling_interval_sec=ONBOARD_POLLING_INTERVAL_SEC,
    )
    service.inventory_api.get_device.assert_called_once_with(device_uid="device-1")
