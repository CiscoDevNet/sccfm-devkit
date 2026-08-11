# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner, Result
from scc_firewall_manager_sdk import CdoCliResult, Device, DevicePage

from cisco_sccfm_cli.cli import cli
from cisco_sccfm_cli.commands.inventory.devices.asa.smartlicense.command import (
    SmartlicenseCommand,
)
from cisco_sccfm_cli.models import Config
from cisco_sccfm_core.services import AsaCommandLineService, InventoryService

_TOKEN_ENVVAR = "SCCFM_SMART_LICENSE_TOKEN"


def test_should_read_smart_license_token_from_environment(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = _sentinel("environment")
    captured = _stub_execution(monkeypatch, sample_devices, sample_cli_results)

    result = cli_runner.invoke(
        cli,
        _command_args(),
        env={_TOKEN_ENVVAR: token},
    )

    assert result.exit_code == 0, result.output
    assert f"license smart register idtoken {token}" in captured["asa_commands"]
    _assert_not_exposed(result, caplog.text, token)


def test_should_read_smart_license_token_from_file(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = _sentinel("file")
    token_file = tmp_path / "smart-license-token"
    token_file.write_text(f"{token}\n", encoding="utf-8")
    captured = _stub_execution(monkeypatch, sample_devices, sample_cli_results)

    result = cli_runner.invoke(
        cli,
        _command_args("--token-file", str(token_file)),
    )

    assert result.exit_code == 0, result.output
    assert f"license smart register idtoken {token}" in captured["asa_commands"]
    _assert_not_exposed(result, caplog.text, token)


def test_should_read_smart_license_token_from_stdin(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = _sentinel("stdin")
    captured = _stub_execution(monkeypatch, sample_devices, sample_cli_results)

    result = cli_runner.invoke(
        cli,
        _command_args("--token-file", "-"),
        input=f"{token}\n",
    )

    assert result.exit_code == 0, result.output
    assert f"license smart register idtoken {token}" in captured["asa_commands"]
    _assert_not_exposed(result, caplog.text, token)


def test_should_prompt_for_smart_license_token_without_echoing_it(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = _sentinel("prompt")
    captured = _stub_execution(monkeypatch, sample_devices, sample_cli_results)
    monkeypatch.setattr(SmartlicenseCommand, "_can_prompt", lambda self: True)

    result = cli_runner.invoke(
        cli,
        _command_args(),
        input=f"{token}\n",
    )

    assert result.exit_code == 0, result.output
    assert "Smart Licensing token:" in result.output
    assert f"license smart register idtoken {token}" in captured["asa_commands"]
    _assert_not_exposed(result, caplog.text, token)


def test_should_fail_noninteractively_without_smart_license_token(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
) -> None:
    captured = _stub_execution(monkeypatch, sample_devices, sample_cli_results)
    monkeypatch.setattr(SmartlicenseCommand, "_can_prompt", lambda self: False)

    result = cli_runner.invoke(cli, _command_args())

    assert result.exit_code != 0
    assert _TOKEN_ENVVAR in result.output
    assert "--token-file" in result.output
    assert "asa_commands" not in captured


def test_should_reject_multiple_smart_license_token_sources_without_exposing_them(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    environment_token = _sentinel("environment-conflict")
    file_token = _sentinel("file-conflict")
    token_file = tmp_path / "smart-license-token"
    token_file.write_text(file_token, encoding="utf-8")
    captured = _stub_execution(monkeypatch, sample_devices, sample_cli_results)

    result = cli_runner.invoke(
        cli,
        _command_args("--token-file", str(token_file)),
        env={_TOKEN_ENVVAR: environment_token},
    )

    assert result.exit_code != 0
    assert "only one Smart Licensing token source" in result.output
    assert "asa_commands" not in captured
    _assert_not_exposed(result, caplog.text, environment_token, file_token)


@pytest.mark.parametrize(
    "token",
    [
        "",
        "token with spaces",
        "token\nwrite memory",
        "token\rwrite memory",
        "token\twrite-memory",
    ],
)
def test_should_reject_invalid_smart_license_tokens_before_execution(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
    token: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    captured = _stub_execution(monkeypatch, sample_devices, sample_cli_results)

    result = cli_runner.invoke(
        cli,
        _command_args("--token", token),
    )

    assert result.exit_code != 0
    assert "Smart Licensing token" in result.output
    assert "asa_commands" not in captured
    if token:
        _assert_not_exposed(result, caplog.text, token)


def test_should_keep_legacy_argv_token_compatible(
    cli_runner: CliRunner,
    default_config: Config,
    mock_inventory_service: None,
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = _sentinel("legacy-argv")
    captured = _stub_execution(monkeypatch, sample_devices, sample_cli_results)

    result = cli_runner.invoke(
        cli,
        _command_args("--token", token),
    )

    assert result.exit_code == 0, result.output
    assert f"license smart register idtoken {token}" in captured["asa_commands"]
    _assert_not_exposed(result, caplog.text, token)


def _command_args(*token_args: str) -> list[str]:
    return [
        "inventory",
        "devices",
        "asa",
        "smartlicense",
        "--device-uids",
        "uid-1",
        "--feature-tier",
        "standard",
        "--format",
        "json",
        *token_args,
    ]


def _stub_execution(
    monkeypatch: MonkeyPatch,
    sample_devices: list[Device],
    sample_cli_results: list[CdoCliResult],
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_get_devices(
        self: InventoryService,
        *,
        limit: int,
        offset: int,
        query: str | None = None,
    ) -> DevicePage:
        return DevicePage(count=len(sample_devices), items=sample_devices)

    def stub_cli_init(self: AsaCommandLineService, config: Any) -> None:
        return None

    def fake_execute_cli(
        self: AsaCommandLineService,
        *,
        device_uids: list[str],
        asa_commands: list[str],
    ) -> list[CdoCliResult]:
        captured["device_uids"] = device_uids
        captured["asa_commands"] = asa_commands
        return sample_cli_results

    monkeypatch.setattr(InventoryService, "get_devices", fake_get_devices)
    monkeypatch.setattr(AsaCommandLineService, "__init__", stub_cli_init)
    monkeypatch.setattr(AsaCommandLineService, "execute_cli", fake_execute_cli)
    return captured


def _sentinel(source: str) -> str:
    return f"sec004-{source}-sentinel-7a29f4"


def _assert_not_exposed(result: Result, log_text: str, *tokens: str) -> None:
    observed = "\n".join(
        [
            result.stdout,
            result.stderr,
            repr(result.exception),
            log_text,
        ]
    )
    for token in tokens:
        if token in observed:
            pytest.fail("Sensitive value was exposed by the CLI.", pytrace=False)
