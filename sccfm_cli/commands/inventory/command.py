from __future__ import annotations

from typing import Any

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.devices import DevicesCommand
from sccfm_cli.commands.inventory.managers import ManagersCommand


class InventoryCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._devices_command = DevicesCommand(console)
        self._managers_command = ManagersCommand(console)

    @property
    def name(self) -> str:
        return "inventory"

    @property
    def help_text(self) -> str:
        return "Browse SCC Firewall Management inventory."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        group.add_command(self._devices_command.build())
        group.add_command(self._managers_command.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail("Specify a subcommand: devices or managers")
