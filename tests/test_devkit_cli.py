# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for secure interactive CLI command construction in the devkit."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from cisco_sccfm_scripts import devkit_cli
from cisco_sccfm_scripts.cli_commands import CliCommand, CliGroup, CliParam, build_cli_tree


class _Prompt:
    """Small questionary prompt stand-in that returns one configured answer."""

    def __init__(self, answer: str | None) -> None:
        self._answer = answer

    def unsafe_ask(self) -> str | None:
        return self._answer


def _find_command(nodes: list[CliGroup | CliCommand], args: list[str]) -> CliCommand:
    for node in nodes:
        if isinstance(node, CliCommand) and node.args == args:
            return node
        if isinstance(node, CliGroup):
            try:
                return _find_command(node.children, args)
            except LookupError:
                continue
    raise LookupError(f"CLI command not found: {args}")


def test_cli_tree_preserves_sensitive_option_metadata() -> None:
    tree = build_cli_tree()
    configure = _find_command(tree, ["configure"])
    asa_onboard = _find_command(
        tree,
        ["inventory", "devices", "asa", "onboard"],
    )
    configure_manager = _find_command(
        tree,
        ["inventory", "devices", "cdfmc-managed-ftd", "configure-manager"],
    )

    api_token = next(param for param in configure.params if param.flag == "--api-token")
    asa_password = next(param for param in asa_onboard.params if param.flag == "--password")
    cli_key = next(param for param in configure_manager.params if param.flag == "--cli-key")

    assert api_token.sensitive
    assert api_token.envvar == "SCCFM_API_TOKEN"
    assert api_token.envvar_list_splitter is None
    assert asa_password.sensitive
    assert asa_password.envvar is None
    assert cli_key.sensitive
    assert cli_key.envvar == "SCCFM_CLI_KEY"
    assert not next(param for param in configure.params if param.flag == "--region").sensitive


@pytest.mark.parametrize(
    ("multiple", "answers", "splitter", "expected_env_value"),
    [
        (False, ["single-secret"], None, "single-secret"),
        (True, ["first-secret", "second-secret", ""], None, "first-secret second-secret"),
        (True, ["first-secret", "second-secret", ""], ":", "first-secret:second-secret"),
    ],
)
def test_sensitive_cli_values_use_hidden_prompts_and_child_only_environment(
    monkeypatch: pytest.MonkeyPatch,
    multiple: bool,
    answers: list[str],
    splitter: str | None,
    expected_env_value: str,
) -> None:
    envvar = "SCCFM_TEST_SECRET"
    monkeypatch.delenv(envvar, raising=False)
    pending: Iterator[str] = iter(answers)
    password_prompts: list[str] = []
    rendered: list[str] = []
    calls: list[tuple[list[str], Path, dict[str, str] | None]] = []

    def fake_password(message: str, **kwargs: Any) -> _Prompt:
        password_prompts.append(message)
        return _Prompt(next(pending))

    def reject_text(message: str, **kwargs: Any) -> _Prompt:
        raise AssertionError(f"sensitive value used a visible prompt: {message}")

    def fake_print(value: object = "", *args: object, **kwargs: object) -> None:
        rendered.append(str(value))

    def fake_call(
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str] | None,
    ) -> int:
        calls.append((list(argv), cwd, None if env is None else dict(env)))
        return 0

    monkeypatch.setattr(devkit_cli.questionary, "password", fake_password)
    monkeypatch.setattr(devkit_cli.questionary, "text", reject_text)
    monkeypatch.setattr(devkit_cli.console, "print", fake_print)
    monkeypatch.setattr(devkit_cli.subprocess, "call", fake_call)

    command = CliCommand(
        name="example",
        description="Example command",
        args=["example"],
        params=[
            CliParam(
                label="Sensitive value",
                flag="--secret",
                required=True,
                multiple=multiple,
                sensitive=True,
                envvar=envvar,
                envvar_list_splitter=splitter,
            )
        ],
    )

    devkit_cli._execute_cli_command(command)

    assert len(calls) == 1
    argv, cwd, child_env = calls[0]
    assert argv == ["sccfm-cli", "example"]
    assert cwd == devkit_cli._project_root()
    assert child_env is not None
    assert child_env[envvar] == expected_env_value
    assert envvar not in os.environ
    assert len(password_prompts) == len(answers)
    display = "\n".join(rendered)
    assert all(answer not in display for answer in answers if answer)


def test_sensitive_cli_value_without_envvar_is_left_to_cli_hidden_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rendered: list[str] = []
    calls: list[tuple[list[str], Path, dict[str, str] | None]] = []

    def reject_prompt(message: str, **kwargs: Any) -> _Prompt:
        raise AssertionError(f"devkit unexpectedly prompted for a delegated secret: {message}")

    def fake_print(value: object = "", *args: object, **kwargs: object) -> None:
        rendered.append(str(value))

    def fake_call(
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str] | None,
    ) -> int:
        calls.append((list(argv), cwd, env))
        return 0

    monkeypatch.setattr(devkit_cli.questionary, "password", reject_prompt)
    monkeypatch.setattr(devkit_cli.questionary, "text", reject_prompt)
    monkeypatch.setattr(devkit_cli.console, "print", fake_print)
    monkeypatch.setattr(devkit_cli.subprocess, "call", fake_call)

    command = CliCommand(
        name="example",
        description="Example command",
        args=["example"],
        params=[
            CliParam(
                label="Sensitive value",
                flag="--secret",
                required=True,
                sensitive=True,
            )
        ],
    )

    devkit_cli._execute_cli_command(command)

    assert calls == [(["sccfm-cli", "example"], devkit_cli._project_root(), None)]
    display = "\n".join(rendered)
    assert "sccfm-cli's hidden prompt" in display
    assert "--secret" not in display
