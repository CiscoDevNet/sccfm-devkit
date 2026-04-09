from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.shared_options import config_path_option, format_option
from sccfm_cli.utils import with_spinner
from sccfm_core.services.policy import AccessGroupListResponse, AccessGroupService


def _access_group_list_params() -> list[click.Parameter]:
    return [
        click.Option(
            ["--limit"],
            type=int,
            default=50,
            show_default=True,
            help="Maximum number of results to return.",
        ),
        click.Option(
            ["--offset"],
            type=int,
            default=0,
            show_default=True,
            help="Pagination offset.",
        ),
        click.Option(
            ["--query"],
            default=None,
            type=str,
            help="Lucene query string to filter results.",
        ),
        format_option(),
        config_path_option(),
    ]


class ListAccessGroupCommand(BaseCommand):
    """List access groups in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "list"

    @property
    def help_text(self) -> str:
        return "List ASA access groups."

    def build_params(self) -> Sequence[click.Parameter]:
        return _access_group_list_params()

    @with_spinner("Fetching access groups...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        config = self.get_profile(ctx=ctx, **kwargs)
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        query = cast(str | None, kwargs.get("query"))
        output_format = cast(str, kwargs.get("format"))

        service = AccessGroupService(config)
        page = service.list_access_groups(limit=limit, offset=offset, query=query)
        self._render_page(page, output_format)

    def _render_page(self, page: AccessGroupListResponse, output_format: str) -> None:
        if output_format == "json":
            self.console.print(json.dumps(page.to_dict(), indent=2, default=str))
            return

        self.console.print(
            f"Showing {page.offset + 1}\u2013{page.offset + len(page.items)} of {page.count} access groups"
        )
        table = Table(title="Access Groups", width=120)
        table.add_column("UID")
        table.add_column("Name")
        table.add_column("Entity UID")
        table.add_column("Shared")
        for item in page.items:
            table.add_row(
                item.uid,
                item.name,
                item.entity_uid,
                str(item.is_shared or False),
            )
        self.console.print(table)
