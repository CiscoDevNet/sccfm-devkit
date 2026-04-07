from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.options import uid_option
from sccfm_cli.commands.shared_options import config_path_option, format_option
from sccfm_cli.utils import with_spinner
from sccfm_core.services.object_management import ObjectOverrideResponse, ObjectOverrideService


class ApplyOverrideAsDefaultObjectCommand(BaseCommand):
    """Apply an override value as the new default for an object."""

    @property
    def name(self) -> str:
        return "apply-override-as-default"

    @property
    def help_text(self) -> str:
        return "Apply an existing override value as the new default value of an object."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            uid_option(),
            click.Option(
                ["--target-id"],
                required=True,
                type=str,
                help="UID of the target device whose override value to apply as the new default.",
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Applying override as default...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        uid = cast(str | None, kwargs.get("uid"))
        target_id = cast(str, kwargs.get("target_id"))
        output_format = cast(str, kwargs.get("format"))

        if not uid:
            ctx.fail("--uid is required.")

        config = self.get_profile(ctx=ctx, **kwargs)
        service = ObjectOverrideService(config)

        try:
            response: ObjectOverrideResponse = service.promote_override(
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
            self.console.print(json.dumps(response.to_dict(), indent=2))
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
        self.console.print("[green]✓[/green] Override applied as default successfully")
        self.console.print(table)
