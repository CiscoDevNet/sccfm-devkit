# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.policies.access_group import AccessGroupCommand
from sccfm_cli.commands.policies.access_rule import AccessRuleCommand


class PoliciesCommand(BaseCommand):
    """Command group for policy management operations."""

    def __init__(self, console: Console) -> None:
        super().__init__(console)
        self._access_group_command = AccessGroupCommand(console)
        self._access_rule_command = AccessRuleCommand(console)

    @property
    def name(self) -> str:
        return "policies"

    @property
    def help_text(self) -> str:
        return "Manage SCC Firewall Management policies."

    def build(self) -> click.Command:
        group = click.Group(name=self.name, help=self.help_text)
        group.add_command(self._access_group_command.build())
        group.add_command(self._access_rule_command.build())
        return group

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:  # pragma: no cover
        ctx.fail("Specify a subcommand: access-group, access-rule")
