from typing import Any, List

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.devices.ftd.list_not_on_version import (
    FtdListNotOnVersionCommand,
)
from sccfm_cli.commands.inventory.devices.ftd.upgrade import FtdUpgradeCommand
from sccfm_cli.commands.inventory.devices.rendering import DeviceListCommand
from sccfm_core import FTD_ENTITY_TYPES


class FtdCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: List[BaseCommand] = [
            DeviceListCommand(
                console,
                entity_types=FTD_ENTITY_TYPES,
                spinner_text="Fetching FTD devices from SCC Firewall Manager...",
                help_text=(
                    "List FTD devices (includes cdFMC-managed, FDM-managed, "
                    "and on-prem FMC-managed FTDs)."
                ),
            ),
            FtdListNotOnVersionCommand(console),
            FtdUpgradeCommand(console),
        ]

    @property
    def name(self) -> str:
        return "ftd"

    @property
    def help_text(self) -> str:
        return "FTD device operations."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        for subcommand in self._subcommands:
            group.add_command(subcommand.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail(f"Specify a subcommand: {', '.join([c.name for c in self._subcommands])}")
