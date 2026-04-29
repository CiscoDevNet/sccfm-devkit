from __future__ import annotations

from typing import Any

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.devices.asa.change_boot_image import (
    AsaChangeBootImageCommand,
)
from sccfm_cli.commands.inventory.devices.asa.cli import AsaCliCommand
from sccfm_cli.commands.inventory.devices.asa.disk import AsaDiskCommand
from sccfm_cli.commands.inventory.devices.asa.ha_check import AsaHaCheckCommand
from sccfm_cli.commands.inventory.devices.asa.list_boot_registry import (
    AsaListBootRegistryCommand,
)
from sccfm_cli.commands.inventory.devices.asa.list_local_users import (
    AsaListLocalUsersCommand,
)
from sccfm_cli.commands.inventory.devices.asa.list_not_on_version import (
    AsaListNotOnVersionCommand,
)
from sccfm_cli.commands.inventory.devices.asa.onboard import AsaOnboardCommand
from sccfm_cli.commands.inventory.devices.asa.shun import AsaShunCommand
from sccfm_cli.commands.inventory.devices.asa.smartlicense.command import SmartlicenseCommand
from sccfm_cli.commands.inventory.devices.asa.upgrade import AsaUpgradeCommand
from sccfm_cli.commands.inventory.devices.asa.user import AsaUserCommand
from sccfm_cli.commands.inventory.devices.rendering import DeviceListCommand
from sccfm_core import ASA_ENTITY_TYPES


class AsaCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: list[BaseCommand] = [
            AsaChangeBootImageCommand(console),
            AsaCliCommand(console),
            AsaDiskCommand(console),
            AsaHaCheckCommand(console),
            DeviceListCommand(
                console,
                entity_types=ASA_ENTITY_TYPES,
                spinner_text="Fetching ASA devices from SCC Firewall Manager...",
                help_text="List ASA devices.",
            ),
            AsaListBootRegistryCommand(console),
            AsaListNotOnVersionCommand(console),
            SmartlicenseCommand(console),
            AsaOnboardCommand(console),
            AsaListLocalUsersCommand(console),
            AsaShunCommand(console),
            AsaUpgradeCommand(console),
            AsaUserCommand(console),
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
