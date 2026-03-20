import time
from typing import Callable, Optional

from scc_firewall_manager_sdk import CdoTransaction, TransactionsApi

from sccfm_core import ApiClientFactory
from sccfm_core.models.cdo_transaction_status import CdoTransactionStatus
from sccfm_core.types import ConfigLike


class TransactionService:
    def __init__(self, config: ConfigLike):
        self.transactions_api = TransactionsApi(ApiClientFactory().build(config=config))

    def get_transaction(self, transaction_uid: str) -> CdoTransaction:
        """Fetch and return the current transaction status by UID."""
        return self.transactions_api.get_transaction(transaction_uid=transaction_uid)

    def wait_for_transaction_to_finish(
        self,
        transaction_uid: str,
        polling_interval_sec: int = 10,
        timeout_sec: int = 300,
        on_poll: Optional[Callable[[CdoTransaction], None]] = None,
    ) -> CdoTransaction:
        start_time = time.time()
        cdo_transaction: CdoTransaction = self.get_transaction(transaction_uid=transaction_uid)
        if on_poll:
            on_poll(cdo_transaction)
        while cdo_transaction.cdo_transaction_status not in [
            CdoTransactionStatus.DONE,
            CdoTransactionStatus.ERROR,
            CdoTransactionStatus.CANCELLED,
        ]:
            elapsed_time = time.time() - start_time
            if elapsed_time >= timeout_sec:
                raise TimeoutError(
                    f"Transaction {transaction_uid} did not complete within {timeout_sec} seconds"
                )
            time.sleep(polling_interval_sec)
            cdo_transaction = self.get_transaction(transaction_uid=transaction_uid)
            if on_poll:
                on_poll(cdo_transaction)
        return cdo_transaction
