# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.options import uid_option
from sccfm_cli.commands.shared_options import config_path_option, format_option
from sccfm_cli.utils import print_json, with_spinner
from sccfm_core.services.object_management import ObjectOverrideResponse, ObjectOverrideService


class EditOverrideObjectCommand(BaseCommand):
    """Edit an existing override value on an object in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "edit-override"

    @property
    def help_text(self) -> str:
        return "Edit the value of an existing override for a specific target device."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            uid_option(),
            click.Option(
                ["--target-id"],
                required=True,
                type=str,
                help="UID of the target device whose override to edit.",
            ),
            click.Option(
                ["--override-value"],
                required=True,
                type=str,
                help="The new override value (IP address, CIDR, range, or URL).",
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Editing override...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        uid = cast(str | None, kwargs.get("uid"))
        target_id = cast(str, kwargs.get("target_id"))
        override_value = cast(str, kwargs.get("override_value"))
        output_format = cast(str, kwargs.get("format"))

        if not uid:
            ctx.fail("--uid is required.")

        config = self.get_profile(ctx=ctx, **kwargs)
        service = ObjectOverrideService(config)

        try:
            response: ObjectOverrideResponse = service.edit_override(
                uid=uid,
                target_id=target_id,
                new_value=override_value,
            )
            self._render_response(response, output_format)
        except ValueError as e:
            ctx.fail(str(e))

    def _render_response(
        self,
        response: ObjectOverrideResponse,
        output_format: str,
    ) -> None:
        if output_format == "json":
            print_json(response.to_dict())
            return

        table = Table(title="Object Override", width=120)
        table.add_column("UID")
        table.add_column("Name")
        table.add_column("Object Type")
        table.add_column("Overrides Count")
        table.add_row(
            response.uid or "-",
            response.name or "-",
            response.object_type or "-",
            str(response.overrides_count),
        )
        self.console.print("[green]✓[/green] Override updated successfully")
        self.console.print(table)
