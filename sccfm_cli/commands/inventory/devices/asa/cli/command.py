from typing import Any, List

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.devices.asa.cli.execute import AsaExecuteCliCommand


class AsaCliCommand(BaseCommand):
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        ctx.fail(f"Specify a subcommand: {', '.join([c.name for c in self._subcommands])}")

    @property
    def name(self) -> str:
        return "cli"

    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: List[BaseCommand] = [
            AsaExecuteCliCommand(console),
        ]

    @property
    def help_text(self) -> str:
        return "ASA device CLI operations."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        for subcommand in self._subcommands:
            group.add_command(subcommand.build())
        return group
