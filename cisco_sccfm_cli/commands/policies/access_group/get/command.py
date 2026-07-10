# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.shared_options import config_path_option, format_option
from cisco_sccfm_cli.utils import print_json, with_spinner
from cisco_sccfm_core.services.policy import AccessGroupResponse, AccessGroupService


def _access_group_get_params() -> list[click.Parameter]:
    return [
        click.Option(
            ["--uid"],
            required=True,
            type=str,
            help="UID of the access group.",
        ),
        format_option(),
        config_path_option(),
    ]


class GetAccessGroupCommand(BaseCommand):
    """Get a single access group by UID."""

    @property
    def name(self) -> str:
        return "get"

    @property
    def help_text(self) -> str:
        return "Get an ASA access group by UID."

    def build_params(self) -> Sequence[click.Parameter]:
        return _access_group_get_params()

    @with_spinner("Fetching access group...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        config = self.get_profile(ctx=ctx, **kwargs)
        uid = cast(str, kwargs["uid"])
        output_format = cast(str, kwargs.get("format"))

        service = AccessGroupService(config)
        response = service.fetch_access_group(uid=uid)
        self._render_response(response, output_format)

    def _render_response(self, response: AccessGroupResponse, output_format: str) -> None:
        if output_format == "json":
            print_json(response.to_dict())
            return

        table = Table(title="Access Group", width=120)
        table.add_column("UID")
        table.add_column("Name")
        table.add_column("Entity UID")
        table.add_column("Shared")
        table.add_row(
            response.uid,
            response.name,
            response.entity_uid,
            str(response.is_shared or False),
        )
        self.console.print(table)
