# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the ``cisco_sccfm_cli transaction`` command."""

from __future__ import annotations

import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from scc_firewall_manager_sdk import CdoTransaction

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.models import Config
from cisco_sccfm_core.services.transaction_service import TransactionService


def _stub_transaction_init(self: TransactionService, config: Any) -> None:
    return None


def _txn(
    uid: str,
    *,
    status: str,
    polling_url: str | None = None,
    error_message: str | None = None,
) -> CdoTransaction:
    return CdoTransaction(
        transactionUid=uid,
        cdoTransactionStatus=status,
        transactionPollingUrl=polling_url,
        errorMessage=error_message,
    )


class TestTransactionCommand:
    def test_should_show_current_status_table(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(TransactionService, "__init__", _stub_transaction_init)
        monkeypatch.setattr(
            TransactionService,
            "get_transaction",
            lambda self, transaction_uid: _txn(
                transaction_uid,
                status="IN_PROGRESS",
                polling_url="https://example/transactions/txn-1",
            ),
        )

        result = cli_runner.invoke(
            cli,
            ["transaction", "--transaction-uid", "txn-1", "--format", "table"],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Transaction UID:" in result.output
        assert "txn-1" in result.output
        assert "Status:" in result.output
        assert "IN_PROGRESS" in result.output
        assert "Polling URL:" in result.output

    def test_should_show_current_status_json(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(TransactionService, "__init__", _stub_transaction_init)
        monkeypatch.setattr(
            TransactionService,
            "get_transaction",
            lambda self, transaction_uid: _txn(transaction_uid, status="DONE"),
        )

        result = cli_runner.invoke(
            cli,
            ["transaction", "--transaction-uid", "txn-json", "--format", "json"],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output)
        assert payload["transactionUid"] == "txn-json"
        assert payload["cdoTransactionStatus"] == "DONE"

    def test_should_wait_and_return_final_status(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(TransactionService, "__init__", _stub_transaction_init)
        monkeypatch.setattr(
            TransactionService,
            "get_transaction",
            lambda self, transaction_uid: _txn(
                transaction_uid,
                status="IN_PROGRESS",
                polling_url="https://example/transactions/txn-wait",
            ),
        )
        monkeypatch.setattr(
            TransactionService,
            "wait_for_transaction_to_finish",
            lambda self, **kwargs: _txn("txn-wait", status="DONE"),
        )

        result = cli_runner.invoke(
            cli,
            [
                "transaction",
                "--transaction-uid",
                "txn-wait",
                "--wait",
                "--format",
                "table",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        # With --wait, UID/Polling URL are printed during wait loop, only Status is printed after.
        assert result.output.count("Transaction UID") == 1
        assert "Status:" in result.output
        assert "DONE" in result.output

    def test_should_exit_nonzero_when_waited_transaction_fails(
        self,
        cli_runner: CliRunner,
        default_config: Config,
        monkeypatch: MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(TransactionService, "__init__", _stub_transaction_init)
        monkeypatch.setattr(
            TransactionService,
            "get_transaction",
            lambda self, transaction_uid: _txn(
                transaction_uid,
                status="IN_PROGRESS",
            ),
        )
        monkeypatch.setattr(
            TransactionService,
            "wait_for_transaction_to_finish",
            lambda self, **kwargs: _txn(
                "txn-fail",
                status="ERROR",
                error_message="Validation failed",
            ),
        )

        result = cli_runner.invoke(
            cli,
            [
                "transaction",
                "--transaction-uid",
                "txn-fail",
                "--wait",
                "--format",
                "table",
            ],
        )

        assert result.exit_code != 0
        assert "Status:" in result.output
        assert "ERROR" in result.output
        assert "Validation failed" in result.output
