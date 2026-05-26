# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.configure import ConfigureCommand
from sccfm_cli.commands.inventory import InventoryCommand
from sccfm_cli.commands.objects import ObjectsCommand
from sccfm_cli.commands.policies import PoliciesCommand
from sccfm_cli.commands.status import StatusCommand
from sccfm_cli.commands.transaction import TransactionCommand


def _build_commands(console: Console) -> list[BaseCommand]:
    return [
        ConfigureCommand(console=console),
        StatusCommand(console=console),
        TransactionCommand(console=console),
        InventoryCommand(console=console),
        ObjectsCommand(console=console),
        PoliciesCommand(console=console),
    ]


def _build_cli() -> click.Group:
    console = Console()

    @click.group(help="SCC Firewall Manager CLI")
    @click.option(
        "--profile",
        default="default",
        show_default=True,
        help="Configuration profile to use",
    )
    @click.option(
        "--silent",
        is_flag=True,
        default=False,
        help="Suppress progress indicators (useful for piping output)",
    )
    @click.pass_context
    def group(ctx: click.Context, profile: str, silent: bool) -> None:
        ctx.ensure_object(dict)
        ctx.obj["profile"] = profile
        ctx.obj["silent"] = silent

    for command in _build_commands(console):
        command.register(group)
    return group


cli = _build_cli()


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        raise SystemExit(130)
