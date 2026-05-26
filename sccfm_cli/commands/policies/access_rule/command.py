# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, List

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.policies.access_rule.create import CreateAccessRuleCommand
from sccfm_cli.commands.policies.access_rule.delete import DeleteAccessRuleCommand
from sccfm_cli.commands.policies.access_rule.get import GetAccessRuleCommand
from sccfm_cli.commands.policies.access_rule.list import ListAccessRuleCommand
from sccfm_cli.commands.policies.access_rule.update import UpdateAccessRuleCommand


class AccessRuleCommand(BaseCommand):
    """Command group for access rule operations."""

    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._subcommands: List[BaseCommand] = [
            CreateAccessRuleCommand(console),
            GetAccessRuleCommand(console),
            ListAccessRuleCommand(console),
            UpdateAccessRuleCommand(console),
            DeleteAccessRuleCommand(console),
        ]

    @property
    def name(self) -> str:
        return "access-rule"

    @property
    def help_text(self) -> str:
        return "Manage ASA access rules."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        for command in self._subcommands:
            group.add_command(command.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail("Specify a subcommand: create, get, list, update, delete")
