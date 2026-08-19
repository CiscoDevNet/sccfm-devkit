# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Discover the installed ``sccfm-cli`` command tree for interactive use."""

from __future__ import annotations

from dataclasses import dataclass, field

import click

from cisco_sccfm_cli.option_metadata import is_sensitive_option

_SKIPPED_PARAMETERS = {"config_path", "help"}


@dataclass(frozen=True)
class InteractiveParameter:
    """A Click option rendered as an interactive prompt."""

    name: str
    label: str
    flag: str
    required: bool
    is_flag: bool
    multiple: bool
    sensitive: bool
    choices: tuple[str, ...]
    secondary_flag: str | None = None


@dataclass(frozen=True)
class InteractiveCommand:
    """A leaf command that can be invoked without a shell subprocess."""

    name: str
    description: str
    path: tuple[str, ...]
    click_command: click.Command = field(repr=False, compare=False)
    parameters: tuple[InteractiveParameter, ...] = ()


@dataclass(frozen=True)
class InteractiveGroup:
    """A navigable group of interactive commands."""

    name: str
    description: str
    children: tuple[InteractiveGroup | InteractiveCommand, ...] = ()


def build_command_tree() -> tuple[InteractiveGroup | InteractiveCommand, ...]:
    """Build the command tree from the installed Click application."""
    from cisco_sccfm_cli.cli import cli

    return _build_children(cli, ())


def _build_children(
    group: click.Group,
    path: tuple[str, ...],
) -> tuple[InteractiveGroup | InteractiveCommand, ...]:
    children: list[InteractiveGroup | InteractiveCommand] = []
    for name, command in sorted(group.commands.items()):
        command_path = (*path, name)
        if isinstance(command, click.Group):
            children.append(
                InteractiveGroup(
                    name=name,
                    description=_first_line(command.help),
                    children=_build_children(command, command_path),
                )
            )
            continue
        children.append(
            InteractiveCommand(
                name=name,
                description=_first_line(command.help),
                path=command_path,
                click_command=command,
                parameters=_parameters(command),
            )
        )
    return tuple(children)


def _parameters(command: click.Command) -> tuple[InteractiveParameter, ...]:
    parameters: list[InteractiveParameter] = []
    for parameter in command.params:
        if not isinstance(parameter, click.Option) or parameter.name in _SKIPPED_PARAMETERS:
            continue
        flag = next((option for option in parameter.opts if option.startswith("--")), None)
        if flag is None:
            continue
        name = parameter.name or flag.lstrip("-").replace("-", "_")
        parameters.append(
            InteractiveParameter(
                name=name,
                label=_first_line(parameter.help) or name.replace("_", " ").title(),
                flag=flag,
                required=bool(parameter.required),
                is_flag=bool(parameter.is_flag),
                multiple=bool(parameter.multiple),
                sensitive=is_sensitive_option(parameter),
                choices=_choices(parameter),
                secondary_flag=next(
                    (option for option in parameter.secondary_opts if option.startswith("--")),
                    None,
                ),
            )
        )
    return tuple(parameters)


def _choices(parameter: click.Option) -> tuple[str, ...]:
    if not isinstance(parameter.type, click.Choice):
        return ()
    return tuple(str(choice) for choice in parameter.type.choices)


def _first_line(text: str | None) -> str:
    if not text:
        return ""
    return text.strip().splitlines()[0].rstrip(".")
