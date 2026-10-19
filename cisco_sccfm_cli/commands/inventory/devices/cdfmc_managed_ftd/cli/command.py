# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from typing import Any, List

import click
from rich.console import Console

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.inventory.devices.cdfmc_managed_ftd.cli.execute import (
    FtdExecuteCliCommand,
)


class FtdCliCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: List[BaseCommand] = [
            FtdExecuteCliCommand(console),
        ]

    @property
    def name(self) -> str:
        return "cli"

    @property
    def help_text(self) -> str:
        return "cdFMC-managed FTD device CLI operations."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        for subcommand in self._subcommands:
            group.add_command(subcommand.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail(f"Specify a subcommand: {', '.join([c.name for c in self._subcommands])}")
