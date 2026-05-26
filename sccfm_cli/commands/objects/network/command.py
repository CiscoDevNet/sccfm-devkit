# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, List

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.network.create import CreateNetworkObjectCommand
from sccfm_cli.commands.objects.network.delete import DeleteNetworkObjectCommand
from sccfm_cli.commands.objects.network.list import ListNetworkObjectCommand
from sccfm_cli.commands.objects.network.update import UpdateNetworkObjectCommand


class NetworkCommand(BaseCommand):
    """Command group for network object operations."""

    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: List[BaseCommand] = [
            CreateNetworkObjectCommand(console),
            ListNetworkObjectCommand(console),
            UpdateNetworkObjectCommand(console),
            DeleteNetworkObjectCommand(console),
        ]

    @property
    def name(self) -> str:
        return "network"

    @property
    def help_text(self) -> str:
        return "Manage network objects."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        for command in self._subcommands:
            group.add_command(command.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail("Specify a subcommand for network (e.g., create, delete).")
