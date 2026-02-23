from __future__ import annotations

from typing import Any, List

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.network_group.create import CreateNetworkGroupCommand


class NetworkGroupCommand(BaseCommand):
    """Command group for network group operations."""

    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: List[BaseCommand] = [
            CreateNetworkGroupCommand(console),
        ]

    @property
    def name(self) -> str:
        return "network-group"

    @property
    def help_text(self) -> str:
        return "Manage network groups."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        for command in self._subcommands:
            group.add_command(command.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail("Specify a subcommand for network-group (e.g., create).")
