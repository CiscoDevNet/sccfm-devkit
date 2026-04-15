from scc_firewall_manager_sdk import AsaCreateOrUpdateInput, CdoTransaction, Device, InventoryApi

from sccfm_core import ApiClientFactory
from sccfm_core.models.cdo_transaction_status import CdoTransactionStatus
from sccfm_core.services.transaction_service import TransactionService
from sccfm_core.types import ConfigLike


class AsaOnboardService:
    def __init__(self, config: ConfigLike) -> None:
        self.inventory_api = InventoryApi(ApiClientFactory().build(config=config))
        self.transaction_service = TransactionService(config=config)

    def onboard_asa(self, asa_create_or_update_input: AsaCreateOrUpdateInput) -> Device:
        transaction: CdoTransaction = self.inventory_api.onboard_asa_device(
            asa_create_or_update_input=asa_create_or_update_input
        )
        completed_transaction: CdoTransaction = (
            self.transaction_service.wait_for_transaction_to_finish(
                transaction_uid=transaction.transaction_uid, polling_interval_sec=5
            )
        )
        if completed_transaction.cdo_transaction_status != CdoTransactionStatus.DONE:
            error_msg = (
                f"Transaction {completed_transaction.transaction_uid} failed with status "
                f"{completed_transaction.cdo_transaction_status}"
            )
            if completed_transaction.error_message:
                error_msg += f": {completed_transaction.error_message}"
            if completed_transaction.error_details:
                error_msg += f" (details: {completed_transaction.error_details})"
            raise Exception(error_msg)

        return self.inventory_api.get_device(device_uid=completed_transaction.entity_uid)
