from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.options import object_update_params, parse_tags
from sccfm_cli.utils import with_spinner
from sccfm_core.errors import NotFoundError
from sccfm_core.services import NetworkObjectService
from sccfm_core.services.object_management import NetworkObjectResponse


class UpdateNetworkObjectCommand(BaseCommand):
    """Update a network object in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "update"

    @property
    def help_text(self) -> str:
        return "Update a network object."

    def build_params(self) -> Sequence[click.Parameter]:
        return object_update_params()

    @with_spinner("Updating network object...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        uid = cast(str | None, kwargs.get("uid"))
        name = cast(str | None, kwargs.get("name"))
        new_name = cast(str | None, kwargs.get("new_name"))
        value = cast(str | None, kwargs.get("value"))
        description = cast(str | None, kwargs.get("description"))
        labels_tuple = kwargs.get("labels")
        labels = list(labels_tuple) if labels_tuple else None
        tags_tuple = cast(tuple[str, ...] | None, kwargs.get("tags"))
        tags = parse_tags(tags_tuple)
        output_format = cast(str, kwargs.get("format"))

        self._validate_identifier(ctx, uid=uid, name=name)
        self._validate_has_updates(
            ctx,
            new_name=new_name,
            value=value,
            description=description,
            labels=labels,
            tags=tags,
        )

        config = self.get_profile(ctx=ctx, **kwargs)
        service = NetworkObjectService(config)

        try:
            response: NetworkObjectResponse = service.update_network_object(
                uid=uid,
                name=name,
                new_name=new_name,
                value=value,
                description=description,
                labels=labels,
                tags=tags,
            )
            self._render_response(response, output_format)
        except NotFoundError as e:
            ctx.fail(str(e))

    @staticmethod
    def _validate_identifier(
        ctx: click.Context,
        *,
        uid: str | None,
        name: str | None,
    ) -> None:
        """Ensure exactly one of --uid or --name is provided."""
        if not uid and not name:
            ctx.fail("Either --uid or --name must be provided.")
        if uid and name:
            ctx.fail("Only one of --uid or --name should be provided, not both.")

    @staticmethod
    def _validate_has_updates(
        ctx: click.Context,
        *,
        new_name: str | None,
        value: str | None,
        description: str | None,
        labels: list[str] | None,
        tags: dict[str, list[str]] | None,
    ) -> None:
        """Ensure at least one updatable field is provided."""
        if not any([new_name, value, description, labels, tags]):
            ctx.fail(
                "At least one update field must be provided: "
                "--new-name, --value, --description, --labels, or --tags."
            )

    def _render_response(
        self,
        response: NetworkObjectResponse,
        output_format: str,
    ) -> None:
        if output_format == "json":
            self.console.print(json.dumps(response.to_dict(), indent=2, default=str))
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
        self.console.print("[green]✓[/green] Network object updated")
        self.console.print(table)
