# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.options import object_list_params
from sccfm_cli.utils import print_json, with_spinner
from sccfm_core.services import NetworkObjectService
from sccfm_core.services.object_management import NetworkObjectListResponse


class ListNetworkObjectCommand(BaseCommand):
    """List network objects in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "list"

    @property
    def help_text(self) -> str:
        return "List network objects."

    def build_params(self) -> Sequence[click.Parameter]:
        return object_list_params()

    @with_spinner("Fetching network objects from SCC Firewall Manager...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        query = cast(str | None, kwargs.get("query"))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        service = NetworkObjectService(config)
        page = service.list_network_objects(
            limit=limit,
            offset=offset,
            query=query,
        )

        self._render_page(page, output_format)

    def _render_page(self, page: NetworkObjectListResponse, output_format: str) -> None:
        if output_format == "json":
            print_json(page.to_dict())
            return

        self.console.print(
            f"Showing {page.offset + 1}–{page.offset + len(page.items)} of {page.count} objects"
        )
        table = Table(title="Network Objects", width=120)
        table.add_column("UID")
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Literal")
        table.add_column("Description")
        for item in page.items:
            table.add_row(
                item.uid or "-",
                item.name or "-",
                item.object_type or "-",
                item.literal or "-",
                item.description or "-",
            )
        self.console.print(table)
