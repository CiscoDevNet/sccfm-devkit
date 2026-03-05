from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.options import (
    format_tags,
    group_update_params,
    parse_tags,
)
from sccfm_cli.commands.objects.utils import (
    check_object_exists,
    validate_has_updates,
    validate_identifier,
)
from sccfm_cli.utils import with_spinner
from sccfm_core.errors import NotFoundError
from sccfm_core.services import NetworkGroupService
from sccfm_core.services.object_management import NetworkGroupResponse


class UpdateNetworkGroupCommand(BaseCommand):
    """Update a network group in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "update"

    @property
    def help_text(self) -> str:
        return "Update a network group."

    def build_params(self) -> Sequence[click.Parameter]:
        return group_update_params()

    @with_spinner("Updating network group...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        uid = cast(str | None, kwargs.get("uid"))
        name = cast(str | None, kwargs.get("name"))
        check = cast(bool, kwargs.get("check", False))
        output_format = cast(str, kwargs.get("format"))

        validate_identifier(ctx, uid=uid, name=name)

        config = self.get_profile(ctx=ctx, **kwargs)
        service = NetworkGroupService(config)

        if check:
            check_object_exists(
                console=self.console,
                uid=uid,
                name=name,
                get_by_uid_fn=service.get_network_group,
                get_by_name_fn=service.get_network_group_by_name,
                object_name="Network group",
                output_format=output_format,
                operation="update",
            )
            return

        new_name = cast(str | None, kwargs.get("new_name"))
        ref_objects_tuple = kwargs.get("referenced_object")
        referenced_objects = list(ref_objects_tuple) if ref_objects_tuple else None
        description = cast(str | None, kwargs.get("description"))
        labels_tuple = kwargs.get("labels")
        labels = list(labels_tuple) if labels_tuple else None
        tags_tuple = cast(tuple[str, ...] | None, kwargs.get("tags"))
        tags = parse_tags(tags_tuple)

        validate_has_updates(
            ctx,
            fields={
                "new_name": new_name,
                "referenced_objects": referenced_objects,
                "description": description,
                "labels": labels,
                "tags": tags,
            },
            field_names=[
                "--new-name",
                "--referenced-object",
                "--description",
                "--labels",
                "--tags",
            ],
        )

        try:
            response: NetworkGroupResponse = service.update_network_group(
                uid=uid,
                name=name,
                new_name=new_name,
                referenced_objects=referenced_objects,
                description=description,
                labels=labels,
                tags=tags,
            )
            self._render_response(response, output_format)
        except NotFoundError as e:
            ctx.fail(str(e))

    def _render_response(
        self,
        response: NetworkGroupResponse,
        output_format: str,
    ) -> None:
        if output_format == "json":
            self.console.print(json.dumps(response.to_dict(), indent=2, default=str))
            return

        self.console.print("[green]✓[/green] Network group updated")
        table = Table(show_header=False, width=80, padding=(0, 1))
        table.add_column("Field", style="bold", width=20)
        table.add_column("Value")
        table.add_row("UID", response.uid or "-")
        table.add_row("Name", response.name or "-")
        table.add_row("Type", response.object_type or "-")
        table.add_row("Description", response.description or "-")
        table.add_row(
            "Labels",
            ", ".join(response.labels) if response.labels else "-",
        )
        table.add_row(
            "Tags",
            format_tags(response.tags) if response.tags else "-",
        )
        table.add_row(
            "Literals",
            "\n".join(response.literals) if response.literals else "-",
        )
        table.add_row(
            "Referenced Objects",
            "\n".join(response.referenced_object_uids) if response.referenced_object_uids else "-",
        )
        self.console.print(table)
