# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import click
import pytest
from click.core import ParameterSource
from click.testing import CliRunner
from pytest import CaptureFixture, MonkeyPatch

from cisco_sccfm_cli import interactive
from cisco_sccfm_cli.interactive_commands import (
    InteractiveCommand,
    InteractiveParameter,
    build_command_tree,
)
from cisco_sccfm_cli.models import Config
from cisco_sccfm_cli.option_metadata import sensitive_option
from cisco_sccfm_cli.services import ConfigService


def test_customer_tasks_are_limited_to_customer_workflows(monkeypatch: MonkeyPatch) -> None:
    actions: list[tuple[str, str]] = []
    monkeypatch.setattr(
        interactive,
        "configure_profile",
        lambda profile: actions.append(("configure-profile", profile)),
    )
    monkeypatch.setattr(
        interactive,
        "manage_profiles",
        lambda profile: actions.append(("manage-profiles", profile)),
    )
    monkeypatch.setattr(
        interactive,
        "run_cli",
        lambda profile: actions.append(("run-cli", profile)),
    )

    tasks = interactive.customer_tasks("lab")
    for task in tasks:
        task.action()

    assert [task.name for task in tasks] == [
        "configure-profile",
        "manage-profiles",
        "run-cli",
    ]
    assert actions == [
        ("configure-profile", "lab"),
        ("manage-profiles", "lab"),
        ("run-cli", "lab"),
    ]


def test_main_passes_global_profile_to_the_menu(monkeypatch: MonkeyPatch) -> None:
    menu = MagicMock()
    monkeypatch.setattr(interactive, "_interactive_menu", menu)

    result = CliRunner().invoke(interactive.main, ["--profile", "lab"])

    assert result.exit_code == 0, result.output
    menu.assert_called_once_with("lab")


def test_configure_profile_masks_token_and_uses_selected_profile(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("SCCFM_CONFIG", str(config_path))
    monkeypatch.setattr(interactive.questionary, "text", _prompt_factory("lab"))
    monkeypatch.setattr(interactive.questionary, "select", _prompt_factory("eu"))
    monkeypatch.setattr(interactive.questionary, "password", _prompt_factory("secret-token"))
    printed = MagicMock()
    monkeypatch.setattr(interactive.console, "print", printed)

    interactive.configure_profile("lab")

    stored = ConfigService(config_path).load("lab")
    assert stored is not None
    assert stored.region == "eu"
    assert stored.api_token == "secret-token"
    assert "secret-token" not in str(printed.call_args_list)


def test_manage_profiles_updates_selected_profile(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.json"
    service = ConfigService(config_path)
    service.save(Config(profile="lab", region="us", api_token="old-token"))
    monkeypatch.setenv("SCCFM_CONFIG", str(config_path))
    monkeypatch.setattr(interactive, "_ask", MagicMock(side_effect=["update", "lab"]))
    monkeypatch.setattr(interactive.questionary, "select", _prompt_factory("eu"))
    monkeypatch.setattr(interactive.questionary, "password", _prompt_factory("new-token"))
    printed = MagicMock()
    monkeypatch.setattr(interactive.console, "print", printed)

    interactive.manage_profiles("lab")

    stored = service.load("lab")
    assert stored is not None
    assert stored.region == "eu"
    assert stored.api_token == "new-token"
    assert "old-token" not in str(printed.call_args_list)
    assert "new-token" not in str(printed.call_args_list)


def test_manage_profiles_removes_selected_profile(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.json"
    service = ConfigService(config_path)
    service.save(Config(profile="lab", region="us", api_token="stored-token"))
    monkeypatch.setenv("SCCFM_CONFIG", str(config_path))
    monkeypatch.setattr(interactive, "_ask", MagicMock(side_effect=["remove", "lab"]))
    monkeypatch.setattr(interactive.questionary, "confirm", _prompt_factory(True))
    printed = MagicMock()
    monkeypatch.setattr(interactive.console, "print", printed)

    interactive.manage_profiles("lab")

    assert service.load("lab") is None
    assert "stored-token" not in str(printed.call_args_list)


def test_command_tree_works_outside_repository_and_marks_secrets(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    tree = build_command_tree()
    configure = next(node for node in tree if node.name == "configure")

    assert isinstance(configure, InteractiveCommand)
    api_token = next(
        parameter for parameter in configure.parameters if parameter.flag == "--api-token"
    )
    assert api_token.sensitive is True


def test_installed_command_tree_can_configure_selected_profile_in_process(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("SCCFM_CONFIG", str(config_path))
    configure = next(node for node in build_command_tree() if node.name == "configure")
    assert isinstance(configure, InteractiveCommand)
    monkeypatch.setattr(
        interactive,
        "_prompt_parameter",
        MagicMock(side_effect=["eu", "profile-secret"]),
    )
    monkeypatch.setattr(interactive.questionary, "confirm", _prompt_factory(True))

    interactive._execute_command(configure, "wheel-user")

    stored = ConfigService(config_path).load("wheel-user")
    assert stored is not None
    assert stored.region == "eu"
    assert stored.api_token == "profile-secret"
    output = capsys.readouterr()
    assert "profile-secret" not in output.out
    assert "profile-secret" not in output.err
    assert "may expose it" not in output.err


def test_execute_command_keeps_secret_out_of_click_args_and_output(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def callback(region: str, api_token: str) -> None:
        context = click.get_current_context()
        captured["region"] = region
        captured["api_token"] = api_token
        captured["profile"] = context.obj["profile"]
        captured["source"] = context.get_parameter_source("api_token")

    command_option = sensitive_option(
        click.Option(["--api-token"], required=True, type=str, hide_input=True)
    )
    click_command = click.Command(
        "configure",
        callback=callback,
        params=[
            click.Option(["--region"], required=True, type=str),
            command_option,
        ],
    )
    command = InteractiveCommand(
        name="configure",
        description="Configure a profile",
        path=("configure",),
        click_command=click_command,
        parameters=(
            InteractiveParameter(
                name="region",
                label="Region",
                flag="--region",
                required=True,
                is_flag=False,
                multiple=False,
                sensitive=False,
                choices=(),
            ),
            InteractiveParameter(
                name="api_token",
                label="API token",
                flag="--api-token",
                required=True,
                is_flag=False,
                multiple=False,
                sensitive=True,
                choices=(),
            ),
        ),
    )
    monkeypatch.setattr(interactive, "_prompt_parameter", MagicMock(side_effect=["us", "secret"]))
    monkeypatch.setattr(interactive.questionary, "confirm", _prompt_factory(True))
    printed = MagicMock()
    monkeypatch.setattr(interactive.console, "print", printed)
    click_args: list[str] = []
    original_make_context = click_command.make_context

    def make_context(info_name: str, args: list[str], **kwargs: Any) -> click.Context:
        click_args.extend(args)
        return original_make_context(info_name, args, **kwargs)

    monkeypatch.setattr(click_command, "make_context", make_context)
    original_sys_argv = ["unrelated-program", "--existing-value"]
    monkeypatch.setattr(sys, "argv", original_sys_argv.copy())

    interactive._execute_command(command, "lab")

    assert captured == {
        "region": "us",
        "api_token": "secret",
        "profile": "lab",
        "source": ParameterSource.PROMPT,
    }
    assert click_args == [
        "--region",
        "us",
        "--api-token",
        interactive._SECRET_PLACEHOLDER,
    ]
    assert "secret" not in str(printed.call_args_list)
    assert "'***'" in str(printed.call_args_list)
    assert sys.argv == original_sys_argv


def test_execute_command_requires_confirmation(monkeypatch: MonkeyPatch) -> None:
    command_callback = MagicMock()
    click_command = click.Command("status", callback=command_callback)
    command = InteractiveCommand(
        name="status",
        description="Check connectivity",
        path=("status",),
        click_command=click_command,
    )
    monkeypatch.setattr(interactive.questionary, "confirm", _prompt_factory(False))

    interactive._execute_command(command, "default")

    command_callback.assert_not_called()


@pytest.mark.parametrize(
    "path",
    [
        ("policies", "access-rule", "create"),
        ("policies", "access-rule", "update"),
    ],
)
def test_dual_boolean_options_offer_the_negative_flag(
    path: tuple[str, ...],
    monkeypatch: MonkeyPatch,
) -> None:
    command = _command_at_path(path)
    active = next(parameter for parameter in command.parameters if parameter.name == "active")
    monkeypatch.setattr(interactive, "_ask", MagicMock(return_value="--inactive"))
    option_args: list[str] = []

    accepted = interactive._collect_parameter(active, option_args, {})

    assert accepted is True
    assert active.flag == "--active"
    assert active.secondary_flag == "--inactive"
    assert option_args == ["--inactive"]


def test_sensitive_prompt_preserves_leading_and_trailing_spaces(
    monkeypatch: MonkeyPatch,
) -> None:
    parameter = InteractiveParameter(
        name="password",
        label="Password",
        flag="--password",
        required=True,
        is_flag=False,
        multiple=False,
        sensitive=True,
        choices=(),
    )
    monkeypatch.setattr(interactive.questionary, "password", _prompt_factory("  pass phrase  "))

    value = interactive._prompt_parameter(parameter, "Password", allow_empty=False)

    assert value == "  pass phrase  "


def test_optional_choice_can_use_the_click_default(monkeypatch: MonkeyPatch) -> None:
    parameter = _parameter(required=False, multiple=False)
    select = _recording_select([""])
    monkeypatch.setattr(interactive.questionary, "select", select)

    answer = interactive._prompt_parameter(parameter, "Output format", allow_empty=True)

    choices = select.call_args.kwargs["choices"]
    assert answer == ""
    assert isinstance(choices[0], interactive.questionary.Choice)
    assert choices[0].title == "<use default>"
    assert choices[0].value == ""


def test_required_multiple_choice_offers_done_after_first_value(
    monkeypatch: MonkeyPatch,
) -> None:
    parameter = _parameter(required=True, multiple=True)
    select = _recording_select(["BASE", ""])
    monkeypatch.setattr(interactive.questionary, "select", select)
    option_args: list[str] = []

    accepted = interactive._collect_multiple(parameter, option_args, {})

    first_choices = select.call_args_list[0].kwargs["choices"]
    second_choices = select.call_args_list[1].kwargs["choices"]
    assert accepted is True
    assert first_choices == ["BASE", "CARRIER"]
    assert isinstance(second_choices[0], interactive.questionary.Choice)
    assert second_choices[0].title == "<done>"
    assert second_choices[0].value == ""
    assert option_args == ["--licenses", "BASE"]


def _prompt_factory(answer: object) -> MagicMock:
    prompt = MagicMock()
    prompt.unsafe_ask.return_value = answer
    return MagicMock(return_value=prompt)


def _recording_select(answers: list[str]) -> MagicMock:
    prompts: list[MagicMock] = []
    for answer in answers:
        prompt = MagicMock()
        prompt.unsafe_ask.return_value = answer
        prompts.append(prompt)
    return MagicMock(side_effect=prompts)


def _parameter(*, required: bool, multiple: bool) -> InteractiveParameter:
    return InteractiveParameter(
        name="licenses",
        label="Licenses",
        flag="--licenses",
        required=required,
        is_flag=False,
        multiple=multiple,
        sensitive=False,
        choices=("BASE", "CARRIER"),
    )


def _command_at_path(path: tuple[str, ...]) -> InteractiveCommand:
    children = build_command_tree()
    node: object | None = None
    for component in path:
        node = next(candidate for candidate in children if candidate.name == component)
        children = node.children if hasattr(node, "children") else ()
    assert isinstance(node, InteractiveCommand)
    return node
