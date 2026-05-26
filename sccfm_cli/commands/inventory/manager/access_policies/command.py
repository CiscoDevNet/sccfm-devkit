# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, List

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.manager.access_policies.list import ListAccessPoliciesCommand


class AccessPoliciesCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: List[BaseCommand] = [
            ListAccessPoliciesCommand(console),
        ]

    @property
    def name(self) -> str:
        return "access-policies"

    @property
    def help_text(self) -> str:
        return "FMC access policy operations."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        for command in self._subcommands:
            group.add_command(command.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail("Specify a subcommand for access-policies (e.g., list).")
