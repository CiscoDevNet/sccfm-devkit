from typing import Any, List

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.devices.ftd.upgrade.compatible_versions import (
    FtdUpgradeCompatibleVersionsCommand,
)


class FtdUpgradeCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: List[BaseCommand] = [
            FtdUpgradeCompatibleVersionsCommand(console),
        ]

    @property
    def name(self) -> str:
        return "upgrade"

    @property
    def help_text(self) -> str:
        return "FTD device upgrade operations."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        for subcommand in self._subcommands:
            group.add_command(subcommand.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail(f"Specify a subcommand: {', '.join([c.name for c in self._subcommands])}")
