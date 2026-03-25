from __future__ import annotations

from typing import Any, List

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.devices.asa import AsaCommand
from sccfm_cli.commands.inventory.devices.cdfmc_managed_ftd import CdfmcManagedFtdCommand
from sccfm_cli.commands.inventory.devices.ftd import FtdCommand
from sccfm_cli.commands.inventory.devices.list import DevicesListCommand


class DevicesCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: List[BaseCommand] = [
            AsaCommand(console),
            FtdCommand(console),
            CdfmcManagedFtdCommand(console),
            DevicesListCommand(console),
        ]

    @property
    def name(self) -> str:
        return "devices"

    @property
    def help_text(self) -> str:
        return "Device inventory operations."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        for command in self._subcommands:
            group.add_command(command.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail("Specify a subcommand for devices (e.g., list).")
