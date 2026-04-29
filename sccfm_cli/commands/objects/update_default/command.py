from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.options import uid_option
from sccfm_cli.commands.shared_options import config_path_option, format_option
from sccfm_cli.utils import print_json, with_spinner
from sccfm_core.services.object_management import ObjectOverrideService, UpdateDefaultValueResponse


class UpdateDefaultObjectCommand(BaseCommand):
    """Update the default value of an object in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "update-default"

    @property
    def help_text(self) -> str:
        return "Update the default content value of an object, preserving all existing overrides."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            uid_option(),
            click.Option(
                ["-v", "--value"],
                required=True,
                type=str,
                help="The new default value (IP address, CIDR, range, or URL).",
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Updating default value...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        uid = cast(str | None, kwargs.get("uid"))
        new_value = cast(str, kwargs.get("value"))
        output_format = cast(str, kwargs.get("format"))

        if not uid:
            ctx.fail("--uid is required.")

        config = self.get_profile(ctx=ctx, **kwargs)
        service = ObjectOverrideService(config)

        try:
            response: UpdateDefaultValueResponse = service.update_default_value(
                uid=uid,
                new_value=new_value,
            )
            self._render_response(response, output_format)
        except ValueError as e:
            ctx.fail(str(e))

    def _render_response(
        self,
        response: UpdateDefaultValueResponse,
        output_format: str,
    ) -> None:
        if output_format == "json":
            print_json(response.to_dict())
            return

        table = Table(title="Object Default Value", width=150)
        table.add_column("UID")
        table.add_column("Name")
        table.add_column("Object Type")
        table.add_column("Default Value")
        table.add_row(
            response.uid or "-",
            response.name or "-",
            response.object_type or "-",
            response.default_value or "-",
        )
        self.console.print("[green]✓[/green] Default value updated successfully")
        self.console.print(table)
