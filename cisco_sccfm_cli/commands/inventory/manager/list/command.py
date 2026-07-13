# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import math
from typing import Any, Sequence, cast

import click
from rich.table import Table
from scc_firewall_manager_sdk import DevicePage

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.inventory.options import inventory_list_params
from cisco_sccfm_cli.utils import print_json, with_spinner
from cisco_sccfm_core.services import InventoryService


class ManagersListCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "list"

    @property
    def help_text(self) -> str:
        return "List manager."

    def build_params(self) -> Sequence[click.Parameter]:
        return inventory_list_params()

    @with_spinner("Fetching managers from SCC Firewall Manager...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        query = cast(str, kwargs.get("query"))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)

        inventory_service = InventoryService(config)
        page: DevicePage = inventory_service.get_managers(
            limit=limit,
            offset=offset,
            query=query,
        )
        self._render_page(page, output_format)

    def _render_page(self, page: DevicePage, output_format: str) -> None:
        if output_format == "json":
            items = page.items or []
            items_dict = [item.to_dict() for item in items]
            print_json(items_dict)
            return

        limit = int(page.limit or len(page.items or []) or 1)
        offset = int(page.offset or 0)
        current_page = (offset // limit) + 1
        total_pages = max(1, math.ceil(page.count / limit)) if page.count else 1

        self.console.print(f"Number of entries:  {page.count}")
        self.console.print(f"Page:               {current_page} / {total_pages}")
        table = Table(title="Managers", width=120)
        table.add_column("UID")
        table.add_column("Name")
        table.add_column("Device Type")
        table.add_column("Software Version")
        table.add_column("Connectivity")
        table.add_column("Configuration")
        table.add_column("FMC Domain UID")
        items = page.items or []
        for device in items:
            table.add_row(
                device.uid,
                device.name,
                device.device_type,
                device.software_version,
                device.connectivity_state,
                device.config_state,
                device.fmc_domain_uid,
            )
        self.console.print(table)
