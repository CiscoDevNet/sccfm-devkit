# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.objects.options import format_tags, group_create_params, parse_tags
from sccfm_cli.commands.objects.utils import check_object_exists
from sccfm_cli.utils import print_json, with_spinner
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
        check = cast(bool, kwargs.get("check", False))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        service = NetworkGroupService(config)

        if check:
            check_object_exists(
                console=self.console,
                uid=None,
                name=name,
                get_by_uid_fn=None,
                get_by_name_fn=service.get_network_group_by_name,
                object_name="Network group",
                output_format=output_format,
                operation="create",
            )
            return

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
            print_json(response.to_dict())
            return

        self.console.print("[green]\u2713[/green] Network group created")
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
