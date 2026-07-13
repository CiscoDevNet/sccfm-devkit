# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

from cisco_sccfm_cli.e2e import _runner
from cisco_sccfm_cli.e2e._runner import _redact_args, _redact_text


def test_should_redact_sensitive_flags_and_explicit_values() -> None:
    cli_key = "configure manager add manager.example secret-key nat-id"
    args = [
        "sccfm-cli",
        "configure-manager",
        "--cli-key",
        cli_key,
        "--ftd-password",
        "password",
        "--name",
        cli_key,
    ]

    redacted = _redact_args(args, (cli_key,))

    assert cli_key not in redacted
    assert "password" not in redacted
    assert redacted == (
        "sccfm-cli",
        "configure-manager",
        "--cli-key",
        "<redacted>",
        "--ftd-password",
        "<redacted>",
        "--name",
        "<redacted>",
    )


def test_should_redact_explicit_values_from_subprocess_output() -> None:
    cli_key = "configure manager add manager.example secret-key nat-id"

    redacted = _redact_text(f"device echoed: {cli_key}", (cli_key,))

    assert redacted == "device echoed: <redacted>"


def test_run_cli_should_not_include_sensitive_value_in_failure(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    cli_key = "configure manager add manager.example secret-key nat-id"
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout=f"device echoed: {cli_key}",
        stderr=f"command failed: {cli_key}",
    )
    monkeypatch.setattr(_runner, "_resolve_binary", lambda: ["sccfm-cli"])
    monkeypatch.setattr(_runner.subprocess, "run", lambda *args, **kwargs: completed)

    with pytest.raises(AssertionError) as exc_info:
        _runner.run_cli(
            "configure-manager",
            "--cli-key",
            cli_key,
            profile="e2e",
            config_path=tmp_path / "config.json",
            sensitive_values=(cli_key,),
        )

    message = str(exc_info.value)
    assert cli_key not in message
    assert message.count("<redacted>") == 3


def test_run_cli_should_retain_secret_json_but_redact_captured_output(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    cli_key = "configure manager add manager.example secret-key nat-id"
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=f'{{"cli_key": "{cli_key}"}}',
        stderr="",
    )
    monkeypatch.setattr(_runner, "_resolve_binary", lambda: ["sccfm-cli"])
    monkeypatch.setattr(_runner.subprocess, "run", lambda *args, **kwargs: completed)

    result = _runner.run_cli(
        "onboard",
        profile="e2e",
        config_path=tmp_path / "config.json",
        redact_json_fields=("cli_key",),
    )

    assert result.json == {"cli_key": cli_key}
    assert cli_key not in result.stdout
    assert result.stdout == '{"cli_key": "<redacted>"}'
    assert cli_key not in repr(result)


def test_run_cli_should_redact_explicit_secret_from_parsed_payload(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    cli_key = "configure manager add manager.example secret-key nat-id"
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=f'{{"cdFmcInfo": {{"cliKey": "{cli_key}"}}}}',
        stderr="",
    )
    monkeypatch.setattr(_runner, "_resolve_binary", lambda: ["sccfm-cli"])
    monkeypatch.setattr(_runner.subprocess, "run", lambda *args, **kwargs: completed)

    result = _runner.run_cli(
        "list",
        profile="e2e",
        config_path=tmp_path / "config.json",
        sensitive_values=(cli_key,),
    )

    assert result.json == {"cdFmcInfo": {"cliKey": "<redacted>"}}
    assert cli_key not in result.stdout


def test_run_cli_timeout_should_suppress_raw_secret_cause(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    cli_key = "configure manager add manager.example secret-key nat-id"
    timeout = subprocess.TimeoutExpired(
        cmd=["sccfm-cli", "--cli-key", cli_key],
        timeout=30,
        output=f"device echoed: {cli_key}",
    )
    monkeypatch.setattr(_runner, "_resolve_binary", lambda: ["sccfm-cli"])

    def raise_timeout(*args: object, **kwargs: object) -> None:
        raise timeout

    monkeypatch.setattr(_runner.subprocess, "run", raise_timeout)

    with pytest.raises(AssertionError) as exc_info:
        _runner.run_cli(
            "configure-manager",
            "--cli-key",
            cli_key,
            profile="e2e",
            config_path=tmp_path / "config.json",
            sensitive_values=(cli_key,),
        )

    assert cli_key not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


def test_run_cli_should_pass_secret_in_environment_without_adding_it_to_argv(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    cli_key = "configure manager add manager.example secret-key nat-id"
    captured: dict[str, Any] = {}

    def complete(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        captured["env"] = kwargs["env"]
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(_runner, "_resolve_binary", lambda: ["sccfm-cli"])
    monkeypatch.setattr(_runner.subprocess, "run", complete)

    result = _runner.run_cli(
        "configure-manager",
        profile="e2e",
        config_path=tmp_path / "config.json",
        sensitive_values=(cli_key,),
        extra_env={"SCCFM_FTD_CLI_KEY": cli_key},
    )

    assert cli_key not in captured["cmd"]
    assert isinstance(captured["env"], dict)
    assert captured["env"]["SCCFM_FTD_CLI_KEY"] == cli_key
    assert cli_key not in result.args
