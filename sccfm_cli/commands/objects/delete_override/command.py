from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.options import uid_option
from sccfm_cli.commands.shared_options import config_path_option, format_option
from sccfm_cli.utils import print_json, with_spinner
from sccfm_core.services.object_management import ObjectOverrideResponse, ObjectOverrideService


class DeleteOverrideObjectCommand(BaseCommand):
    """Delete an existing override from an object in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "delete-override"

    @property
    def help_text(self) -> str:
        return "Delete an existing override for a specific target device."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            uid_option(),
            click.Option(
                ["--target-id"],
                required=True,
                type=str,
                help="UID of the target device whose override to delete.",
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Deleting override...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        uid = cast(str | None, kwargs.get("uid"))
        target_id = cast(str, kwargs.get("target_id"))
        output_format = cast(str, kwargs.get("format"))

        if not uid:
            ctx.fail("--uid is required.")

        config = self.get_profile(ctx=ctx, **kwargs)
        service = ObjectOverrideService(config)

        try:
            response: ObjectOverrideResponse = service.delete_override(
                uid=uid,
                target_id=target_id,
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
        self.console.print("[green]✓[/green] Override deleted successfully")
        self.console.print(table)
