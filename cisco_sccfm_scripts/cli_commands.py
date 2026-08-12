# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Dynamic sccfm-cli command tree built by introspecting the Click group.

Any command added to sccfm-cli is automatically available in the devkit
interactive runner — no changes to this file are required.

Infrastructure options that are not useful in an interactive session
(``--help``, ``--config-path``) are filtered out automatically.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import click

from cisco_sccfm_cli.option_metadata import is_sensitive_option

# Options that are wired up at the infrastructure level and should not be
# prompted for interactively.
_SKIP_PARAMS = {"help", "config_path"}


@dataclass
class CliParam:
    label: str
    flag: str  # e.g. "--query"
    required: bool
    is_flag: bool = False  # True for boolean toggle options (e.g. --check)
    multiple: bool = False  # True for repeatable options (e.g. --labels, --tags)
    sensitive: bool = False  # True when the option value must be handled as a secret
    envvar: str | tuple[str, ...] | None = None
    envvar_list_splitter: str | None = None


@dataclass
class CliCommand:
    name: str
    description: str
    args: list[str]
    params: list[CliParam] = field(default_factory=list)


@dataclass
class CliGroup:
    name: str
    description: str
    children: list[CliGroup | CliCommand] = field(default_factory=list)


def _first_line(text: str | None) -> str:
    """Return the first non-empty line of a help string."""
    if not text:
        return ""
    return text.strip().splitlines()[0].rstrip(".")


def _envvar_metadata(envvar: str | Sequence[str] | None) -> str | tuple[str, ...] | None:
    """Return immutable Click envvar metadata for the interactive runner."""
    if envvar is None or isinstance(envvar, str):
        return envvar
    return tuple(envvar)


def _build_tree(group: click.Group, args_prefix: list[str]) -> list[CliGroup | CliCommand]:
    """Recursively build a CliGroup/CliCommand tree from a Click group."""
    result: list[CliGroup | CliCommand] = []
    for name, cmd in sorted(group.commands.items()):
        if isinstance(cmd, click.Group):
            children = _build_tree(cmd, args_prefix + [name])
            result.append(
                CliGroup(
                    name=name,
                    description=_first_line(cmd.help),
                    children=children,
                )
            )
        elif isinstance(cmd, click.Command):
            params: list[CliParam] = []
            for param in cmd.params:
                if not isinstance(param, click.Option):
                    continue
                if param.name in _SKIP_PARAMS:
                    continue
                # Prefer the long form (--name) over the short form (-n) for clarity.
                flag = next((o for o in param.opts if o.startswith("--")), param.opts[0])
                label = _first_line(param.help) or (param.name or flag).replace("_", " ").title()
                params.append(
                    CliParam(
                        label=label,
                        flag=flag,
                        required=bool(param.required),
                        is_flag=bool(param.is_flag),
                        multiple=bool(param.multiple),
                        sensitive=is_sensitive_option(param),
                        envvar=_envvar_metadata(param.envvar),
                        envvar_list_splitter=param.type.envvar_list_splitter,
                    )
                )
            result.append(
                CliCommand(
                    name=name,
                    description=_first_line(cmd.help),
                    args=args_prefix + [name],
                    params=params,
                )
            )
    return result


def build_cli_tree() -> list[CliGroup | CliCommand]:
    """Return the full sccfm-cli command tree by introspecting the Click CLI."""
    from cisco_sccfm_cli.cli import cli as _root

    return _build_tree(_root, [])
