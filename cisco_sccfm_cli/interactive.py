#!/usr/bin/env python3

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Customer-facing interactive entry point for ``sccfm-cli``."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from functools import partial
from typing import Callable, Final, TypeAlias

import click
import questionary
from click.core import ParameterSource
from rich.console import Console
from rich.panel import Panel

from cisco_sccfm_cli.interactive_commands import (
    InteractiveCommand,
    InteractiveGroup,
    InteractiveParameter,
    build_command_tree,
)
from cisco_sccfm_cli.models import Config
from cisco_sccfm_cli.services import ConfigService
from cisco_sccfm_core.constants import SCCFM_REGIONS

console = Console()

_SECRET_PLACEHOLDER: Final[str] = "__SCCFM_INTERACTIVE_SECRET__"
_SecretValue: TypeAlias = str | tuple[str, ...]


@dataclass(frozen=True)
class CustomerTask:
    """A customer-safe task shared by the public and development menus."""

    name: str
    description: str
    action: Callable[[], None]


def customer_tasks(profile: str = "default") -> tuple[CustomerTask, ...]:
    """Return the customer-facing tasks bound to the selected profile."""
    return (
        CustomerTask(
            "configure-profile",
            "Create or replace an SCCFM profile",
            partial(configure_profile, profile),
        ),
        CustomerTask(
            "manage-profiles",
            "Update or remove SCCFM profiles",
            partial(manage_profiles, profile),
        ),
        CustomerTask(
            "run-cli",
            "Run an sccfm-cli command interactively",
            partial(run_cli, profile),
        ),
    )


def configure_profile(profile: str = "default") -> None:
    """Create or replace a profile in the canonical SCCFM profile store."""
    profile_answer = questionary.text("Profile name:", default=profile).unsafe_ask()
    selected_profile = _normalized_answer(profile_answer)
    if not selected_profile:
        console.print("[red]Profile name cannot be empty.[/red]")
        return

    region_answer = questionary.select(
        "SCCFM region:",
        choices=list(SCCFM_REGIONS),
        default="us",
    ).unsafe_ask()
    region = _normalized_answer(region_answer)
    if not region:
        console.print("[dim]Cancelled.[/dim]")
        return

    token_answer = questionary.password("SCCFM API token:").unsafe_ask()
    api_token = _normalized_answer(token_answer)
    if not api_token:
        console.print("[red]API token cannot be empty.[/red]")
        return

    ConfigService().save(Config(profile=selected_profile, region=region, api_token=api_token))
    console.print(f"[green]Profile '{selected_profile}' configured for region '{region}'.[/green]")


def manage_profiles(profile: str = "default") -> None:
    """Update or remove profiles in the canonical SCCFM profile store."""
    answer = _ask(("update", "remove", "back"), "Manage profiles:")
    if answer == "update":
        _update_profile(profile)
    elif answer == "remove":
        _remove_profile(profile)


def run_cli(profile: str = "default") -> None:
    """Navigate and invoke installed ``sccfm-cli`` commands."""
    _navigate(build_command_tree(), "sccfm-cli", profile)


def _update_profile(preferred_profile: str) -> None:
    selected = _select_profile("Select a profile to update:", preferred_profile)
    if selected is None:
        return

    region_answer = questionary.select(
        "SCCFM region:",
        choices=list(SCCFM_REGIONS),
        default=selected.region,
    ).unsafe_ask()
    region = _normalized_answer(region_answer)
    if not region:
        console.print("[dim]Cancelled.[/dim]")
        return

    token_answer = questionary.password(
        "New SCCFM API token (leave blank to keep the current token):"
    ).unsafe_ask()
    api_token = _normalized_answer(token_answer) or selected.api_token
    ConfigService().save(Config(profile=selected.profile, region=region, api_token=api_token))
    console.print(f"[green]Profile '{selected.profile}' updated.[/green]")


def _remove_profile(preferred_profile: str) -> None:
    selected = _select_profile("Select a profile to remove:", preferred_profile)
    if selected is None:
        return

    confirmed = questionary.confirm(
        f"Remove profile '{selected.profile}' (region={selected.region})?",
        default=False,
    ).unsafe_ask()
    if not confirmed:
        console.print("[dim]Cancelled.[/dim]")
        return

    ConfigService().remove(selected.profile)
    console.print(f"[green]Profile '{selected.profile}' removed.[/green]")


def _select_profile(message: str, preferred_profile: str) -> Config | None:
    profiles = ConfigService().list_profiles()
    if not profiles:
        console.print("[yellow]No SCCFM profiles configured.[/yellow]")
        return None

    choices = [
        questionary.Choice(title=f"{item.profile}  ({item.region})", value=item.profile)
        for item in profiles
    ]
    choices.append(questionary.Choice(title="back", value="back"))
    default = (
        preferred_profile if any(item.profile == preferred_profile for item in profiles) else None
    )
    answer = _ask(choices, message, default=default)
    if answer is None or answer == "back":
        return None
    return next((item for item in profiles if item.profile == answer), None)


def _navigate(
    children: tuple[InteractiveGroup | InteractiveCommand, ...],
    title: str,
    profile: str,
) -> None:
    while True:
        choices = [
            questionary.Choice(
                title=f"{node.name:20s} {node.description}",
                value=node.name,
            )
            for node in children
        ]
        choices.append(questionary.Choice(title="back", value="back"))
        answer = _ask(choices, f"{title}:")
        if answer is None or answer == "back":
            return

        node = next((candidate for candidate in children if candidate.name == answer), None)
        if isinstance(node, InteractiveGroup):
            _navigate(node.children, f"{title} > {node.name}", profile)
        elif isinstance(node, InteractiveCommand):
            _execute_command(node, profile)


def _execute_command(command: InteractiveCommand, profile: str) -> None:
    option_args: list[str] = []
    secret_values: dict[str, _SecretValue] = {}
    for parameter in command.parameters:
        if not _collect_parameter(parameter, option_args, secret_values):
            return

    display_args = ["sccfm-cli", "--profile", profile, *command.path, *option_args]
    console.print(f"$ {_render_command(display_args)}", style="bold cyan", markup=False)
    confirmed = questionary.confirm("Run this command?", default=False).unsafe_ask()
    if not confirmed:
        console.print("[dim]Cancelled.[/dim]")
        return
    _invoke_command(command, profile, option_args, secret_values)


def _collect_parameter(
    parameter: InteractiveParameter,
    option_args: list[str],
    secret_values: dict[str, _SecretValue],
) -> bool:
    if parameter.is_flag:
        return _collect_flag(parameter, option_args)
    if parameter.multiple:
        return _collect_multiple(parameter, option_args, secret_values)
    return _collect_single(parameter, option_args, secret_values)


def _collect_flag(parameter: InteractiveParameter, option_args: list[str]) -> bool:
    if parameter.secondary_flag is None:
        enabled = questionary.confirm(f"{parameter.label}?", default=False).unsafe_ask()
        if enabled:
            option_args.append(parameter.flag)
        return True

    choices: list[questionary.Choice] = []
    if not parameter.required:
        choices.append(questionary.Choice(title="<use default>", value=""))
    choices.extend(
        questionary.Choice(title=flag.removeprefix("--"), value=flag)
        for flag in (parameter.flag, parameter.secondary_flag)
    )
    selected = _ask(choices, f"{parameter.label}:")
    if selected:
        option_args.append(selected)
    return True


def _collect_multiple(
    parameter: InteractiveParameter,
    option_args: list[str],
    secret_values: dict[str, _SecretValue],
) -> bool:
    console.print(f"[dim]{parameter.label} — enter one value per line, blank to finish:[/dim]")
    values: list[str] = []
    while True:
        value = _prompt_parameter(
            parameter,
            f"  {parameter.flag}",
            allow_empty=bool(values) or not parameter.required,
        )
        if not value:
            break
        values.append(value)
        option_args.extend([parameter.flag, _argument_value(parameter, value)])
    if parameter.required and not values:
        console.print(f"[red]{parameter.label} is required.[/red]")
        return False
    if parameter.sensitive and values:
        secret_values[parameter.name] = tuple(values)
    return True


def _collect_single(
    parameter: InteractiveParameter,
    option_args: list[str],
    secret_values: dict[str, _SecretValue],
) -> bool:
    suffix = "" if parameter.required else " (leave blank to skip)"
    value = _prompt_parameter(
        parameter,
        f"{parameter.label}{suffix}",
        allow_empty=not parameter.required,
    )
    if not value:
        if parameter.required:
            console.print(f"[red]{parameter.label} is required.[/red]")
            return False
        return True

    option_args.extend([parameter.flag, _argument_value(parameter, value)])
    if parameter.sensitive:
        secret_values[parameter.name] = value
    return True


def _argument_value(parameter: InteractiveParameter, value: str) -> str:
    return _SECRET_PLACEHOLDER if parameter.sensitive else value


def _prompt_parameter(
    parameter: InteractiveParameter,
    message: str,
    *,
    allow_empty: bool,
) -> str:
    if parameter.sensitive:
        answer = questionary.password(message).unsafe_ask()
    elif parameter.choices:
        choices: list[questionary.Choice | str] = list(parameter.choices)
        if allow_empty:
            empty_title = "<done>" if parameter.multiple else "<use default>"
            choices.insert(0, questionary.Choice(title=empty_title, value=""))
        answer = questionary.select(message, choices=choices).unsafe_ask()
    else:
        answer = questionary.text(message).unsafe_ask()
    if parameter.sensitive and isinstance(answer, str):
        return answer if answer.strip() else ""
    return _normalized_answer(answer)


def _invoke_command(
    command: InteractiveCommand,
    profile: str,
    option_args: list[str],
    secret_values: dict[str, _SecretValue],
) -> None:
    from cisco_sccfm_cli.cli import cli

    root_context = click.Context(
        cli,
        info_name="sccfm-cli",
        obj={"profile": profile, "silent": False},
    )
    try:
        with root_context:
            with command.click_command.make_context(
                command.name,
                option_args,
                parent=root_context,
            ) as command_context:
                _inject_secrets(command_context, secret_values)
                command.click_command.invoke(command_context)
    except click.ClickException as exc:
        exc.show()
    except click.Abort:
        console.print("[yellow]Cancelled.[/yellow]")
    except click.exceptions.Exit:
        return
    except SystemExit:
        return


def _inject_secrets(context: click.Context, secret_values: dict[str, _SecretValue]) -> None:
    for name, value in secret_values.items():
        context.params[name] = value
        context.set_parameter_source(name, ParameterSource.PROMPT)


def _render_command(arguments: list[str]) -> str:
    redacted = ["***" if value == _SECRET_PLACEHOLDER else value for value in arguments]
    return shlex.join(redacted)


def _normalized_answer(answer: object) -> str:
    return answer.strip() if isinstance(answer, str) else ""


def _ask(
    choices: list[questionary.Choice | str] | tuple[str, ...],
    message: str,
    *,
    default: str | None = None,
) -> str | None:
    answer = questionary.select(
        message,
        choices=choices,
        default=default,
        use_search_filter=True,
        use_jk_keys=False,
    ).unsafe_ask()
    return answer if isinstance(answer, str) else None


def _interactive_menu(profile: str) -> None:
    tasks = customer_tasks(profile)
    console.print(
        Panel(
            "[bold]SCCFM CLI Interactive[/bold]\nSelect a task to run.",
            border_style="cyan",
        )
    )
    choices = [
        questionary.Choice(
            title=f"{task.name:20s} {task.description}",
            value=task.name,
        )
        for task in tasks
    ]
    choices.append(questionary.Choice(title="exit", value="exit"))
    task_by_name = {task.name: task for task in tasks}

    while True:
        try:
            answer = _ask(choices, "What would you like to do?")
            if answer is None or answer == "exit":
                break
            console.print()
            task = task_by_name.get(answer)
            if task is not None:
                task.action()
            console.print()
        except KeyboardInterrupt:
            console.print("\n[yellow]Exiting.[/yellow]")
            break
    console.print("[dim]Bye![/dim]")


@click.command(help="Open the customer-facing interactive SCCFM CLI menu.")
@click.option(
    "--profile",
    default="default",
    show_default=True,
    help="Configuration profile to use when running sccfm-cli commands.",
)
def main(profile: str) -> None:
    """Open the customer-facing interactive SCCFM CLI menu."""
    _interactive_menu(profile)


if __name__ == "__main__":
    main()
