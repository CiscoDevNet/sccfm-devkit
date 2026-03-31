from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.options import uid_option
from sccfm_cli.commands.shared_options import config_path_option, format_option
from sccfm_cli.utils import with_spinner
from sccfm_core.services.object_management import ObjectOverrideService, ObjectTargetsResponse


class GetObjectTargetsCommand(BaseCommand):
    """List the devices an object is attached to in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "get-targets"

    @property
    def help_text(self) -> str:
        return "List the devices an object is attached to. The target IDs can be used with add-override."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            uid_option(),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Fetching object targets...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        uid = cast(str | None, kwargs.get("uid"))
        output_format = cast(str, kwargs.get("format"))

        if not uid:
            ctx.fail("--uid is required.")

        config = self.get_profile(ctx=ctx, **kwargs)
        service = ObjectOverrideService(config)

        response: ObjectTargetsResponse = service.get_targets(uid=uid)
        self._render_response(response, output_format)

    def _render_response(
        self,
        response: ObjectTargetsResponse,
        output_format: str,
    ) -> None:
        if output_format == "json":
            self.console.print(json.dumps(response.to_dict(), indent=2))
            return

        if not response.targets:
            self.console.print(
                f"[yellow]Object '{response.name}' is not attached to any device.[/yellow]"
            )
            return

        table = Table(title=f"Targets for '{response.name}'", width=120)
        table.add_column("ID")
        table.add_column("Display Name")
        table.add_column("Type")
        for target in response.targets:
            table.add_row(
                target.id or "-",
                target.display_name or "-",
                target.type or "-",
            )
        self.console.print(table)
