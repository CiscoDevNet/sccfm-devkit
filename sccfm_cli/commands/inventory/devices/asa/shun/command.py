from __future__ import annotations

from typing import Any, List

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.devices.asa.shun.add import AddShunCommand
from sccfm_cli.commands.inventory.devices.asa.shun.clear import ClearShunCommand
from sccfm_cli.commands.inventory.devices.asa.shun.remove import RemoveShunCommand
from sccfm_cli.commands.inventory.devices.asa.shun.show import ShowShunCommand


class AsaShunCommand(BaseCommand):
    """Command group for ASA shun operations."""

    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: List[BaseCommand] = [
            AddShunCommand(console),
            ShowShunCommand(console),
            RemoveShunCommand(console),
            ClearShunCommand(console),
        ]

    @property
    def name(self) -> str:
        return "shun"

    @property
    def help_text(self) -> str:
        return "Manage shun entries on ASA devices."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        for subcommand in self._subcommands:
            group.add_command(subcommand.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail("Specify a subcommand: add, show, remove, clear")
