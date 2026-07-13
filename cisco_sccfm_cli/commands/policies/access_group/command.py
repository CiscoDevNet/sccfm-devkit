# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, List

import click
from rich.console import Console

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.policies.access_group.get import GetAccessGroupCommand
from cisco_sccfm_cli.commands.policies.access_group.list import ListAccessGroupCommand


class AccessGroupCommand(BaseCommand):
    """Command group for access group operations."""

    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: List[BaseCommand] = [
            GetAccessGroupCommand(console),
            ListAccessGroupCommand(console),
        ]

    @property
    def name(self) -> str:
        return "access-group"

    @property
    def help_text(self) -> str:
        return "List and inspect ASA access groups."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        for command in self._subcommands:
            group.add_command(command.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail("Specify a subcommand: get, list")
