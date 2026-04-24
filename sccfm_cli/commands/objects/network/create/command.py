from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.options import object_create_params, parse_tags
from sccfm_cli.commands.objects.utils import check_object_exists
from sccfm_cli.utils import print_json, with_spinner
from sccfm_core.services import NetworkObjectService
from sccfm_core.services.object_management import NetworkObjectResponse


class CreateNetworkObjectCommand(BaseCommand):
    """Create a network object in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "create"

    @property
    def help_text(self) -> str:
        return "Create a network object."

    def build_params(self) -> Sequence[click.Parameter]:
        return object_create_params()

    @with_spinner("Creating network object...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        name = cast(str, kwargs.get("name"))
        check = cast(bool, kwargs.get("check", False))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        service = NetworkObjectService(config)

        if check:
            check_object_exists(
                console=self.console,
                uid=None,
                name=name,
                get_by_uid_fn=None,
                get_by_name_fn=service.get_network_object_by_name,
                object_name="Network object",
                output_format=output_format,
                operation="create",
            )
            return

        value = cast(str, kwargs.get("value"))
        if not value:
            ctx.fail("--value is required when not using --check.")

        description = cast(str | None, kwargs.get("description"))
        labels_tuple = kwargs.get("labels")
        labels = list(labels_tuple) if labels_tuple else None
        tags_tuple = cast(tuple[str, ...] | None, kwargs.get("tags"))
        tags = parse_tags(tags_tuple)

        response: NetworkObjectResponse = service.create_network_object(
            name=name,
            value=value,
            description=description,
            labels=labels,
            tags=tags,
        )

        self._render_response(response, output_format)

    def _render_response(self, response: NetworkObjectResponse, output_format: str) -> None:
        if output_format == "json":
            print_json(response.to_dict())
            return

        table = Table(title="Network Object", width=120)
        table.add_column("UID")
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Literal")
        table.add_row(
            response.uid or "-",
            response.name or "-",
            response.object_type or "-",
            response.literal or "-",
        )
        self.console.print("[green]\u2713[/green] Network object created")
        self.console.print(table)
