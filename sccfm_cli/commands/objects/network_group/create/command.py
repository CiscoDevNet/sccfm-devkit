from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.options import group_create_params, parse_tags
from sccfm_cli.utils import with_spinner
from sccfm_core.services import NetworkGroupService
from sccfm_core.services.object_management import NetworkGroupResponse


class CreateNetworkGroupCommand(BaseCommand):
    """Create a network group in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "create"

    @property
    def help_text(self) -> str:
        return "Create a network group."

    def build_params(self) -> Sequence[click.Parameter]:
        return group_create_params()

    @with_spinner("Creating network group...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        name = cast(str, kwargs.get("name"))
        ref_objects_tuple = kwargs.get("referenced_object")
        referenced_objects = list(ref_objects_tuple) if ref_objects_tuple else None
        network_literals_tuple = kwargs.get("network_literal")
        network_literals = list(network_literals_tuple) if network_literals_tuple else None
        url_literals_tuple = kwargs.get("url_literal")
        url_literals = list(url_literals_tuple) if url_literals_tuple else None

        if network_literals and url_literals:
            ctx.fail(
                "Only one literal type is allowed per group. "
                "Use --network-literal or --url-literal, not both."
            )

        if not referenced_objects and not network_literals and not url_literals:
            ctx.fail(
                "At least one --referenced-object, --network-literal, or "
                "--url-literal is required to create a network group."
            )
        description = cast(str | None, kwargs.get("description"))
        labels_tuple = kwargs.get("labels")
        labels = list(labels_tuple) if labels_tuple else None
        tags_tuple = cast(tuple[str, ...] | None, kwargs.get("tags"))
        tags = parse_tags(tags_tuple)
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        service = NetworkGroupService(config)
        response: NetworkGroupResponse = service.create_network_group(
            name=name,
            network_literals=network_literals,
            url_literals=url_literals,
            referenced_objects=referenced_objects,
            description=description,
            labels=labels,
            tags=tags,
        )

        self._render_response(response, output_format)

    def _render_response(self, response: NetworkGroupResponse, output_format: str) -> None:
        if output_format == "json":
            self.console.print(json.dumps(response.to_dict(), indent=2, default=str))
            return

        table = Table(title="Network Group", width=120)
        table.add_column("UID")
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Literals")
        table.add_column("Referenced Objects")
        table.add_row(
            response.uid or "-",
            response.name or "-",
            response.object_type or "-",
            ", ".join(response.literals) if response.literals else "-",
            ", ".join(response.referenced_object_uids) if response.referenced_object_uids else "-",
        )
        self.console.print("[green]✓[/green] Network group created")
        self.console.print(table)
