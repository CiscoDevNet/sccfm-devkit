# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from rich.table import Table

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.objects.options import format_tags, group_member_mutation_params
from cisco_sccfm_cli.commands.objects.utils import (
    check_object_exists,
    check_referenced_objects_exist,
    validate_identifier,
)
from cisco_sccfm_cli.utils import print_json, with_spinner
from cisco_sccfm_core.errors import NotFoundError
from cisco_sccfm_core.services import NetworkGroupService, NetworkObjectService
from cisco_sccfm_core.services.object_management import (
    NetworkGroupMemberMutationResult,
    NetworkGroupResponse,
)


class AddNetworkGroupMemberCommand(BaseCommand):
    """Add referenced network-object members to a network group."""

    @property
    def name(self) -> str:
        return "add-member"

    @property
    def help_text(self) -> str:
        return "Add referenced network-object members to a network group."

    def build_params(self) -> Sequence[click.Parameter]:
        return group_member_mutation_params()

    @with_spinner("Adding network group members...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        uid = cast(str | None, kwargs.get("uid"))
        name = cast(str | None, kwargs.get("name"))
        check = cast(bool, kwargs.get("check", False))
        output_format = cast(str, kwargs.get("format"))

        validate_identifier(ctx, uid=uid, name=name)

        config = self.get_profile(ctx=ctx, **kwargs)
        service = NetworkGroupService(config)

        if check:
            ref_objects_tuple = cast(tuple[str, ...] | None, kwargs.get("referenced_object"))
            if output_format == "json" and ref_objects_tuple:
                group_check = check_object_exists(
                    console=self.console,
                    uid=uid,
                    name=name,
                    get_by_uid_fn=service.get_network_group,
                    get_by_name_fn=service.get_network_group_by_name,
                    object_name="Network group",
                    output_format=output_format,
                    operation="update",
                    emit=False,
                )
                obj_service = NetworkObjectService(config)
                ref_checks = check_referenced_objects_exist(
                    console=self.console,
                    referenced_objects=list(ref_objects_tuple),
                    obj_service=obj_service,
                    output_format=output_format,
                    emit=False,
                )
                print_json(
                    {
                        "target": group_check,
                        "referenced_objects": ref_checks,
                    }
                )
                return

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
            if ref_objects_tuple:
                obj_service = NetworkObjectService(config)
                check_referenced_objects_exist(
                    console=self.console,
                    referenced_objects=list(ref_objects_tuple),
                    obj_service=obj_service,
                    output_format=output_format,
                )
            return

        ref_objects_tuple = cast(tuple[str, ...] | None, kwargs.get("referenced_object"))
        referenced_objects = list(ref_objects_tuple) if ref_objects_tuple else None
        if not referenced_objects:
            ctx.fail("At least one --referenced-object must be provided.")

        try:
            result = service.add_network_group_members(
                uid=uid,
                name=name,
                referenced_objects=referenced_objects,
            )
            self._render_response(result, output_format)
        except NotFoundError as e:
            ctx.fail(str(e))

    def _render_response(
        self,
        result: NetworkGroupMemberMutationResult,
        output_format: str,
    ) -> None:
        response = result.network_group
        if output_format == "json":
            print_json(response.to_dict())
            return

        if result.changed:
            self.console.print("[green]✓[/green] Network group members added")
        else:
            self.console.print(
                "[yellow]![/yellow] Network group already contains all requested members"
            )
        self._print_table(response)

    def _print_table(self, response: NetworkGroupResponse) -> None:
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
