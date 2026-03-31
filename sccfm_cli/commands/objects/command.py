from __future__ import annotations

from typing import Any

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.add_override.command import AddOverrideObjectCommand
from sccfm_cli.commands.objects.delete_override.command import DeleteOverrideObjectCommand
from sccfm_cli.commands.objects.edit_override.command import EditOverrideObjectCommand
from sccfm_cli.commands.objects.show.command import ShowObjectCommand
from sccfm_cli.commands.objects.network import NetworkCommand
from sccfm_cli.commands.objects.network_group import NetworkGroupCommand
from sccfm_cli.commands.objects.apply_override_as_default.command import ApplyOverrideAsDefaultObjectCommand
from sccfm_cli.commands.objects.update_default.command import UpdateDefaultObjectCommand


class ObjectsCommand(BaseCommand):
    """Command group for object management operations."""

    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._network_command = NetworkCommand(console)
        self._network_group_command = NetworkGroupCommand(console)
        self._add_override_command = AddOverrideObjectCommand(console)
        self._update_default_command = UpdateDefaultObjectCommand(console)
        self._edit_override_command = EditOverrideObjectCommand(console)
        self._delete_override_command = DeleteOverrideObjectCommand(console)
        self._promote_override_command = ApplyOverrideAsDefaultObjectCommand(console)
        self._show_command = ShowObjectCommand(console)

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
        group.add_command(self._update_default_command.build())
        group.add_command(self._edit_override_command.build())
        group.add_command(self._delete_override_command.build())
        group.add_command(self._promote_override_command.build())
        group.add_command(self._show_command.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail("Specify a subcommand: network, network-group")
