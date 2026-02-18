from typing import Any, List

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.devices.asa.cli import AsaCliCommand
from sccfm_cli.commands.inventory.devices.asa.disk import AsaDiskCommand
from sccfm_cli.commands.inventory.devices.asa.list_local_users.command import (
    AsaListLocalUsersCommand,
)
from sccfm_cli.commands.inventory.devices.asa.onboard import AsaOnboardCommand
from sccfm_cli.commands.inventory.devices.asa.smartlicense.command import SmartlicenseCommand


class AsaCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: List[BaseCommand] = [
            AsaCliCommand(console),
            AsaDiskCommand(console),
            SmartlicenseCommand(console),
            AsaOnboardCommand(console),
            AsaListLocalUsersCommand(console),
        ]

    @property
    def name(self) -> str:
        return "asa"

    @property
    def help_text(self) -> str:
        return "ASA device operations."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        for subcommand in self._subcommands:
            group.add_command(subcommand.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail(f"Specify a subcommand: {', '.join([c.name for c in self._subcommands])}")
