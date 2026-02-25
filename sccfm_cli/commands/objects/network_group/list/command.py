from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.options import object_list_params
from sccfm_cli.utils import with_spinner
from sccfm_core.services import NetworkGroupService
from sccfm_core.services.object_management import NetworkGroupListResponse


class ListNetworkGroupCommand(BaseCommand):
    """List network groups in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "list"

    @property
    def help_text(self) -> str:
        return "List network groups."

    def build_params(self) -> Sequence[click.Parameter]:
        return object_list_params()

    @with_spinner("Fetching network groups from SCC Firewall Manager...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        query = cast(str | None, kwargs.get("query"))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        service = NetworkGroupService(config)
        page = service.list_network_groups(
            limit=limit,
            offset=offset,
            query=query,
        )

        self._render_page(page, output_format)

    def _render_page(self, page: NetworkGroupListResponse, output_format: str) -> None:
        if output_format == "json":
            self.console.print(json.dumps(page.to_dict(), indent=2, default=str))
            return

        self.console.print(
            f"Showing {page.offset + 1}–{page.offset + len(page.items)} of {page.count} groups"
        )
        table = Table(title="Network Groups", width=120)
        table.add_column("UID")
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Literals")
        table.add_column("Refs")
        table.add_column("Description")
        for item in page.items:
            literals_display = ", ".join(item.literals[:3])
            if len(item.literals) > 3:
                literals_display += f" (+{len(item.literals) - 3})"
            refs_display = ", ".join(item.referenced_object_uids[:2])
            if len(item.referenced_object_uids) > 2:
                refs_display += f" (+{len(item.referenced_object_uids) - 2})"
            table.add_row(
                item.uid or "-",
                item.name or "-",
                item.object_type or "-",
                literals_display or "-",
                refs_display or "-",
                item.description or "-",
            )
        self.console.print(table)
