# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import traceback
from typing import Any

import click
import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner, Result
from scc_firewall_manager_sdk import (
    ApiException,
    CdoCliResult,
    CdoTransaction,
    Device,
    DevicePage,
    EntityType,
)

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.models import Config
from cisco_sccfm_cli.utils.redaction import REDACTED_VALUE
from cisco_sccfm_core.services import AsaCommandLineService, InventoryService

_TOKEN_ENVVAR = "SCCFM_SMART_LICENSE_TOKEN"
_SYNTHETIC_TOKEN = "sec004-sensitive-output-sentinel-5d91f"


@pytest.mark.parametrize("output_format", ["table", "json"])
def test_should_redact_sensitive_cli_result_fields(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    output_format: str,
) -> None:
    device = _sensitive_device()
    result_model = CdoCliResult(
        uid=f"result-{_SYNTHETIC_TOKEN}",
        device_uid=device.uid,
        execution_uid=f"execution-{_SYNTHETIC_TOKEN}",
        result=f"result containing {_SYNTHETIC_TOKEN}",
        error_msg=f"error containing {_SYNTHETIC_TOKEN}",
        script=f"license smart register idtoken {_SYNTHETIC_TOKEN}",
    )
    captured = _stub_cli_execution(monkeypatch, device, [result_model])

    result = _invoke(cli_runner, output_format)

    assert result.exit_code == 0, result.output
    _assert_raw_token_reached_service(captured)
    _assert_redacted_everywhere(result, caplog.text)


@pytest.mark.parametrize("output_format", ["table", "json"])
def test_should_redact_sensitive_failed_transaction_fields(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    output_format: str,
) -> None:
    device = _sensitive_device()
    transaction = CdoTransaction(
        cdo_transaction_status="ERROR",
        entity_uid=f"entity-{_SYNTHETIC_TOKEN}",
        entity_url=f"https://example.invalid/{_SYNTHETIC_TOKEN}",
        error_details={"failure": _SYNTHETIC_TOKEN},
        error_message=f"transaction failed with {_SYNTHETIC_TOKEN}",
        tenant_uid=f"tenant-{_SYNTHETIC_TOKEN}",
        transaction_details={
            f"key-{_SYNTHETIC_TOKEN}": f"detail-{_SYNTHETIC_TOKEN}",
            "script": f"license smart register idtoken {_SYNTHETIC_TOKEN}",
        },
        transaction_polling_url=f"https://example.invalid/poll/{_SYNTHETIC_TOKEN}",
        transaction_type="EXECUTE_CLI_COMMAND",
        transaction_uid=f"transaction-{_SYNTHETIC_TOKEN}",
    )
    captured = _stub_cli_execution(monkeypatch, device, transaction)

    result = _invoke(cli_runner, output_format)

    assert result.exit_code != 0
    _assert_raw_token_reached_service(captured)
    _assert_redacted_everywhere(result, caplog.text)


@pytest.mark.parametrize("output_format", ["table", "json"])
def test_should_redact_sensitive_api_exception_body_and_details(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    output_format: str,
) -> None:
    error_body = json.dumps(
        {
            "errorMsg": f"API failure containing {_SYNTHETIC_TOKEN}",
            "errorCode": f"CODE-{_SYNTHETIC_TOKEN}",
            "details": {
                f"key-{_SYNTHETIC_TOKEN}": f"detail-{_SYNTHETIC_TOKEN}",
                "script": f"license smart register idtoken {_SYNTHETIC_TOKEN}",
            },
        }
    )
    _stub_inventory_failure(
        monkeypatch,
        ApiException(status=400, reason=f"reason-{_SYNTHETIC_TOKEN}", body=error_body),
    )

    result = _invoke(cli_runner, output_format)

    assert result.exit_code != 0
    _assert_redacted_everywhere(result, caplog.text)


def test_should_redact_runtime_error_before_handle_registers_token(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _stub_inventory_failure(
        monkeypatch,
        RuntimeError(f"inventory failure containing {_SYNTHETIC_TOKEN}"),
    )

    result = _invoke(cli_runner, "table")

    assert result.exit_code != 0
    _assert_redacted_everywhere(result, caplog.text)


def test_should_redact_click_exception_before_handle_registers_token(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _stub_inventory_failure(
        monkeypatch,
        click.ClickException(f"validation failure containing {_SYNTHETIC_TOKEN}"),
    )

    result = _invoke(cli_runner, "table")

    assert result.exit_code != 0
    _assert_redacted_everywhere(result, caplog.text)


def _invoke(cli_runner: CliRunner, output_format: str) -> Result:
    return cli_runner.invoke(
        cli,
        [
            "inventory",
            "devices",
            "asa",
            "smartlicense",
            "--device-uids",
            "requested-device",
            "--feature-tier",
            "standard",
            "--format",
            output_format,
        ],
        env={_TOKEN_ENVVAR: _SYNTHETIC_TOKEN},
    )


def _sensitive_device() -> Device:
    device = Device(
        uid=f"device-{_SYNTHETIC_TOKEN}",
        name=f"asa-{_SYNTHETIC_TOKEN}",
        device_type=EntityType.ASA,
    )
    device.hardware_model = "ASA5516-X"
    return device


def _stub_cli_execution(
    monkeypatch: MonkeyPatch,
    device: Device,
    response: list[CdoCliResult] | CdoTransaction,
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_get_devices(
        self: InventoryService,
        *,
        limit: int,
        offset: int,
        query: str | None = None,
    ) -> DevicePage:
        return DevicePage(count=1, items=[device])

    def stub_cli_init(self: AsaCommandLineService, config: Any) -> None:
        return None

    def fake_execute_cli(
        self: AsaCommandLineService,
        *,
        device_uids: list[str],
        asa_commands: list[str],
    ) -> list[CdoCliResult] | CdoTransaction:
        captured["device_uids"] = device_uids
        captured["asa_commands"] = asa_commands
        return response

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaCommandLineService, "__init__", stub_cli_init)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)
    return captured


def _stub_inventory_failure(monkeypatch: MonkeyPatch, error: Exception) -> None:
    def fake_get_devices(
        self: InventoryService,
        *,
        limit: int,
        offset: int,
        query: str | None = None,
    ) -> DevicePage:
        raise error

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)


def _assert_raw_token_reached_service(captured: dict[str, Any]) -> None:
    commands = captured["asa_commands"]
    assert isinstance(commands, list)
    assert f"license smart register idtoken {_SYNTHETIC_TOKEN}" in commands


def _assert_redacted_everywhere(result: Result, log_text: str) -> None:
    surfaces = (
        result.stdout,
        result.stderr,
        _exception_chain_text(result.exception),
        "".join(traceback.format_exception(*result.exc_info)) if result.exc_info else "",
        log_text,
    )
    if any(_SYNTHETIC_TOKEN in surface for surface in surfaces):
        pytest.fail("Sensitive value was exposed by the CLI.", pytrace=False)
    assert REDACTED_VALUE in f"{result.stdout}\n{result.stderr}"


def _exception_chain_text(exception: BaseException | None) -> str:
    pending = [exception] if exception is not None else []
    seen: set[int] = set()
    rendered: list[str] = []
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        rendered.extend((repr(current), repr(vars(current))))
        if current.__context__ is not None:
            pending.append(current.__context__)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
    return "\n".join(rendered)
