# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import time
from collections.abc import Callable

from scc_firewall_manager_sdk import CdoTransaction, TransactionsApi

from cisco_sccfm_core import ApiClientFactory
from cisco_sccfm_core.constants import (
    DEFAULT_POLLING_INTERVAL_SEC,
    DEFAULT_TRANSACTION_TIMEOUT_SEC,
)
from cisco_sccfm_core.models.cdo_transaction_status import CdoTransactionStatus
from cisco_sccfm_core.types import ConfigLike


class TransactionService:
    def __init__(self, config: ConfigLike):
        self.transactions_api = TransactionsApi(ApiClientFactory().build(config=config))

    def get_transaction(self, *, transaction_uid: str) -> CdoTransaction:
        """Fetch and return the current transaction status by UID."""
        return self.transactions_api.get_transaction(transaction_uid=transaction_uid)

    def wait_for_transaction_to_finish(
        self,
        transaction_uid: str,
        polling_interval_sec: int = DEFAULT_POLLING_INTERVAL_SEC,
        timeout_sec: int = DEFAULT_TRANSACTION_TIMEOUT_SEC,
        on_poll: Callable[[CdoTransaction], None] | None = None,
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
