# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import math
from typing import Any, Sequence, cast

import click
from rich.table import Table

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.shared_options import (
    config_path_option,
    format_option,
    limit_option,
    offset_option,
)
from cisco_sccfm_cli.utils import print_json, with_spinner
from cisco_sccfm_core.services.policy import AccessRuleListResponse, AccessRuleService


def _access_rule_list_params() -> list[click.Parameter]:
    return [
        limit_option(),
        offset_option(),
        click.Option(
            ["--query"],
            default=None,
            type=str,
            help="Lucene query string to filter results.",
        ),
        format_option(),
        config_path_option(),
    ]


class ListAccessRuleCommand(BaseCommand):
    """List access rules in SCC Firewall Manager."""

    @property
    def name(self) -> str:
        return "list"

    @property
    def help_text(self) -> str:
        return "List ASA access rules."

    def build_params(self) -> Sequence[click.Parameter]:
        return _access_rule_list_params()

    @with_spinner("Fetching access rules...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        config = self.get_profile(ctx=ctx, **kwargs)
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        query = cast(str | None, kwargs.get("query"))
        output_format = cast(str, kwargs.get("format"))

        service = AccessRuleService(config)
        page = service.list_access_rules(limit=limit, offset=offset, query=query)
        self._render_page(page, output_format)

    def _render_page(self, page: AccessRuleListResponse, output_format: str) -> None:
        if output_format == "json":
            print_json(page.to_dict())
            return

        current_page = (page.offset // page.limit) + 1 if page.limit else 1
        total_pages = max(1, math.ceil(page.count / page.limit)) if page.count and page.limit else 1
        self.console.print(f"Number of entries:  {page.count}")
        self.console.print(f"Page:               {current_page} / {total_pages}")
        table = Table(title="Access Rules", width=120)
        table.add_column("UID")
        table.add_column("Action")
        table.add_column("Source")
        table.add_column("Destination")
        table.add_column("Protocol")
        table.add_column("Dest Port")
        table.add_column("Index")
        for item in page.items:
            src = (item.source_network or {}).get("name", "any")
            dst = (item.destination_network or {}).get("name", "any")
            proto = (item.protocol or {}).get("name", "ip")
            dport = (item.destination_port or {}).get("name", "any")
            table.add_row(
                item.uid,
                item.rule_action or "-",
                src,
                dst,
                proto,
                dport,
                str(item.index),
            )
        self.console.print(table)
