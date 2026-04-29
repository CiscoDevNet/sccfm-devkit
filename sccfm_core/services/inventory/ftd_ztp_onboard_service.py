from __future__ import annotations

from scc_firewall_manager_sdk import CdoTransaction, Device, InventoryApi, ZtpOnboardingInput

from sccfm_core import ApiClientFactory
from sccfm_core.constants import ONBOARD_POLLING_INTERVAL_SEC
from sccfm_core.models.cdo_transaction_status import CdoTransactionStatus
from sccfm_core.services.transaction_service import TransactionService
from sccfm_core.types import ConfigLike


class FtdZtpOnboardService:
    def __init__(self, config: ConfigLike) -> None:
        self.inventory_api = InventoryApi(ApiClientFactory().build(config=config))
        self.transaction_service = TransactionService(config=config)

    def onboard_ftd_ztp(self, ztp_onboarding_input: ZtpOnboardingInput) -> Device:
        transaction: CdoTransaction = self.inventory_api.onboard_ftd_device_using_ztp(
            ztp_onboarding_input=ztp_onboarding_input
        )
        completed_transaction: CdoTransaction = (
            self.transaction_service.wait_for_transaction_to_finish(
                transaction_uid=transaction.transaction_uid,
                polling_interval_sec=ONBOARD_POLLING_INTERVAL_SEC,
            )
        )
        if completed_transaction.cdo_transaction_status != CdoTransactionStatus.DONE:
            raise Exception(
                f"Transaction {completed_transaction.transaction_uid} failed with status "
                f"{completed_transaction.cdo_transaction_status}"
            )

        return self.inventory_api.get_device(device_uid=completed_transaction.entity_uid)
