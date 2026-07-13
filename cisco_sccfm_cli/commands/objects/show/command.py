# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.objects.options import uid_option
from cisco_sccfm_cli.commands.shared_options import config_path_option, format_option
from cisco_sccfm_cli.utils import print_json, with_spinner
from cisco_sccfm_core.services.object_management import ObjectDetailsResponse, ObjectOverrideService


class ShowObjectCommand(BaseCommand):
    """Show the full details of an object in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "show"

    @property
    def help_text(self) -> str:
        return "Show the full details of an object, including its default value, overrides, and targets."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            uid_option(),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Fetching object...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        uid = cast(str | None, kwargs.get("uid"))
        output_format = cast(str, kwargs.get("format"))

        if not uid:
            ctx.fail("--uid is required.")

        config = self.get_profile(ctx=ctx, **kwargs)
        service = ObjectOverrideService(config)

        try:
            response: ObjectDetailsResponse = service.get_object(uid=uid)
            self._render_response(response, output_format)
        except ValueError as e:
            ctx.fail(str(e))

    def _render_response(
        self,
        response: ObjectDetailsResponse,
        output_format: str,
    ) -> None:
        if output_format == "json":
            print_json(response.to_dict())
            return

        # Summary table
        summary = Table(title=f"Object: {response.name}", width=120)
        summary.add_column("Field", style="bold")
        summary.add_column("Value")
        summary.add_row("UID", response.uid or "-")
        summary.add_row("Name", response.name or "-")
        summary.add_row("Type", response.object_type or "-")
        summary.add_row("Default Value", response.default_value or "-")
        summary.add_row("Description", response.description or "-")
        self.console.print(summary)

        # Targets table
        if response.targets:
            targets_table = Table(title="Targets", width=120)
            targets_table.add_column("ID")
            targets_table.add_column("Display Name")
            targets_table.add_column("Type")
            for target in response.targets:
                targets_table.add_row(
                    target.id or "-",
                    target.display_name or "-",
                    target.type or "-",
                )
            self.console.print(targets_table)
        else:
            self.console.print("[yellow]No devices attached.[/yellow]")

        # Overrides table
        if response.overrides:
            overrides_table = Table(title="Overrides", width=120)
            overrides_table.add_column("Target ID")
            overrides_table.add_column("Override Value")
            for override in response.overrides:
                overrides_table.add_row(
                    override.target_id or "-",
                    override.value or "-",
                )
            self.console.print(overrides_table)
        else:
            self.console.print("[dim]No overrides configured.[/dim]")
