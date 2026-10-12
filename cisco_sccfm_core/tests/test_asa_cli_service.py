# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from unittest.mock import Mock

import pytest
from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction

from cisco_sccfm_core.constants import FAST_POLLING_INTERVAL_SEC
from cisco_sccfm_core.services.inventory.asa_cli_service import (
    AsaCommandLineService,
    is_failed_cli_result,
)

DEVICE_UID = "11111111-1111-4111-8111-111111111111"


def test_execute_cli_waits_and_returns_cli_results() -> None:
    service = AsaCommandLineService.__new__(AsaCommandLineService)
    service.command_line_interface_api = Mock()
    service.transaction_service = Mock()

    service.command_line_interface_api.execute_cli_command.return_value = CdoTransaction(
        transactionUid="txn-1"
    )
    service.transaction_service.wait_for_transaction_to_finish.return_value = CdoTransaction(
        transactionUid="txn-1",
        cdoTransactionStatus="DONE",
        entityUid="execution-1",
    )
    cli_result = CdoCliResult(
        uid="result-1",
        device_uid=DEVICE_UID,
        execution_uid="execution-1",
        result="ASA Version",
        script="show version\nshow failover",
        error_msg=None,
    )
    service.command_line_interface_api.get_cli_results.return_value = Mock(items=[cli_result])

    results = service.execute_cli(
        device_uids=[DEVICE_UID],
        asa_commands=["show version", "show failover"],
    )

    assert results == [cli_result]
    command_input = service.command_line_interface_api.execute_cli_command.call_args.kwargs[
        "cli_command_input"
    ]
    assert command_input.device_uids == [DEVICE_UID]
    assert command_input.script == "show version\nshow failover"
    service.transaction_service.wait_for_transaction_to_finish.assert_called_once_with(
        transaction_uid="txn-1",
        polling_interval_sec=FAST_POLLING_INTERVAL_SEC,
    )
    service.command_line_interface_api.get_cli_results.assert_called_once_with(
        q="executionUid:execution-1"
    )


def test_get_cli_result_uses_keyword_uid() -> None:
    service = AsaCommandLineService.__new__(AsaCommandLineService)
    service.command_line_interface_api = Mock()
    expected = Mock()
    service.command_line_interface_api.get_cli_result.return_value = expected

    result = service.get_cli_result(cli_result_uid="result-1")

    assert result is expected
    service.command_line_interface_api.get_cli_result.assert_called_once_with(
        cli_result_uid="result-1"
    )


@pytest.mark.parametrize(
    ("result_text", "error_msg", "expected"),
    [
        ("Cisco Adaptive Security Appliance Software Version 9.4(1)200", None, False),
        ("", None, False),
        (None, None, False),
        ("Command failed", None, True),
        ("access-list ok\nERROR: % Invalid input detected at '^' marker.", None, True),
        ("", "Device unreachable", True),
        ("hostname ERROR:-not-a-prefix", None, False),
    ],
)
def test_is_failed_cli_result_detects_per_device_failures(
    result_text: str | None, error_msg: str | None, expected: bool
) -> None:
    result = CdoCliResult(uid="r1", deviceUid=DEVICE_UID, result=result_text, errorMsg=error_msg)

    assert is_failed_cli_result(result) is expected
