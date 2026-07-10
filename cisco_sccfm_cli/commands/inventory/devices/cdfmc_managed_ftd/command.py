# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from typing import Any, List

import click
from rich.console import Console
from scc_firewall_manager_sdk import EntityType

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.inventory.devices.cdfmc_managed_ftd.cli import FtdCliCommand
from cisco_sccfm_cli.commands.inventory.devices.cdfmc_managed_ftd.configure_manager import (
    FtdConfigureManagerCommand,
)
from cisco_sccfm_cli.commands.inventory.devices.cdfmc_managed_ftd.deploy import FtdDeployCommand
from cisco_sccfm_cli.commands.inventory.devices.cdfmc_managed_ftd.onboard import FtdOnboardCommand
from cisco_sccfm_cli.commands.inventory.devices.cdfmc_managed_ftd.onboard_ztp import (
    FtdZtpOnboardCommand,
)
from cisco_sccfm_cli.commands.inventory.devices.rendering import DeviceListCommand


class CdfmcManagedFtdCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: List[BaseCommand] = [
            FtdCliCommand(console),
            DeviceListCommand(
                console,
                entity_types=[EntityType.CDFMC_MANAGED_FTD],
                spinner_text="Fetching cdFMC-managed FTD devices from SCC Firewall Manager...",
                help_text="List cdFMC-managed FTD devices.",
            ),
            FtdDeployCommand(console),
            FtdOnboardCommand(console),
            FtdZtpOnboardCommand(console),
            FtdConfigureManagerCommand(console),
        ]

    @property
    def name(self) -> str:
        return "cdfmc-managed-ftd"

    @property
    def help_text(self) -> str:
        return "cdFMC-managed FTD device operations."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        for subcommand in self._subcommands:
            group.add_command(subcommand.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail(f"Specify a subcommand: {', '.join([c.name for c in self._subcommands])}")
