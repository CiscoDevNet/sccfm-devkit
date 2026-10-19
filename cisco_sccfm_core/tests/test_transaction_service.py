# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from unittest.mock import Mock

from scc_firewall_manager_sdk import CdoTransaction

from cisco_sccfm_core.services.transaction_service import TransactionService


def test_get_transaction_uses_keyword_transaction_uid() -> None:
    service = TransactionService.__new__(TransactionService)
    service.transactions_api = Mock()
    expected = CdoTransaction(transactionUid="txn-1", cdoTransactionStatus="DONE")
    service.transactions_api.get_transaction.return_value = expected

    result = service.get_transaction(transaction_uid="txn-1")

    assert result is expected
    service.transactions_api.get_transaction.assert_called_once_with(transaction_uid="txn-1")


def test_wait_for_transaction_returns_when_initial_status_is_terminal() -> None:
    service = TransactionService.__new__(TransactionService)
    service.transactions_api = Mock()
    expected = CdoTransaction(transactionUid="txn-1", cdoTransactionStatus="DONE")
    service.transactions_api.get_transaction.return_value = expected

    result = service.wait_for_transaction_to_finish(transaction_uid="txn-1")

    assert result is expected
    service.transactions_api.get_transaction.assert_called_once_with(transaction_uid="txn-1")
