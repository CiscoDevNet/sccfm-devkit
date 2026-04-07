from __future__ import annotations

from typing import Any, List

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.manager.access_policies import AccessPoliciesCommand
from sccfm_cli.commands.inventory.manager.list import ManagersListCommand


class ManagersCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: List[BaseCommand] = [
            ManagersListCommand(console),
            AccessPoliciesCommand(console),
        ]

    @property
    def name(self) -> str:
        return "manager"

    @property
    def help_text(self) -> str:
        return "Manager inventory operations."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        for command in self._subcommands:
            group.add_command(command.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail("Specify a subcommand for manager (e.g., list).")
