from __future__ import annotations

from typing import Any

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.add_override.command import AddOverrideObjectCommand
from sccfm_cli.commands.objects.get_targets.command import GetObjectTargetsCommand
from sccfm_cli.commands.objects.network import NetworkCommand
from sccfm_cli.commands.objects.network_group import NetworkGroupCommand


class ObjectsCommand(BaseCommand):
    """Command group for object management operations."""

    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._network_command = NetworkCommand(console)
        self._network_group_command = NetworkGroupCommand(console)
        self._add_override_command = AddOverrideObjectCommand(console)
        self._get_targets_command = GetObjectTargetsCommand(console)

    @property
    def name(self) -> str:
        return "objects"

    @property
    def help_text(self) -> str:
        return "Manage SCC Firewall Management objects."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        group.add_command(self._network_command.build())
        group.add_command(self._network_group_command.build())
        group.add_command(self._add_override_command.build())
        group.add_command(self._get_targets_command.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail("Specify a subcommand: network, network-group")
