from __future__ import annotations

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.configure import ConfigureCommand
from sccfm_cli.commands.inventory import InventoryCommand
from sccfm_cli.commands.status import StatusCommand


def _build_commands(console: Console) -> list[BaseCommand]:
    return [
        ConfigureCommand(console=console),
        StatusCommand(console=console),
        InventoryCommand(console=console),
    ]


def _build_cli() -> click.Group:
    console = Console()

    @click.group(help="SCC Firewall Manager CLI")  # type: ignore[misc]
    @click.option(
        "--profile",
        default="default",
        show_default=True,
        help="Configuration profile to use",
    )  # type: ignore[misc]
    @click.pass_context  # type: ignore[misc]
    def group(ctx: click.Context, profile: str) -> None:
        ctx.ensure_object(dict)
        ctx.obj["profile"] = profile

    for command in _build_commands(console):
        command.register(group)
    return group


cli = _build_cli()


if __name__ == "__main__":
    cli()
