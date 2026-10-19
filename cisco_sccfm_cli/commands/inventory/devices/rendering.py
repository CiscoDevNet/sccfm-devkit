# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import math
from typing import Any, Sequence, cast

import click
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from scc_firewall_manager_sdk import DevicePage, EntityType

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.inventory.options import inventory_list_params
from cisco_sccfm_cli.utils import print_json
from cisco_sccfm_core import build_device_type_filter
from cisco_sccfm_core.services import InventoryService


def render_device_page(
    console: Console,
    page: DevicePage,
    output_format: str,
    *,
    limit: int,
    offset: int,
) -> None:
    """Render a :class:`DevicePage` as JSON or a Rich table."""
    if output_format == "json":
        items = page.items or []
        items_dict = [item.to_dict() for item in items]
        print_json(items_dict)
        return

    current_page = (offset // limit) + 1
    total_pages = max(1, math.ceil(page.count / limit)) if page.count else 1

    console.print(f"Number of entries:  {page.count}")
    console.print(f"Page:               {current_page} / {total_pages}")
    table = Table(title="Devices", width=120)
    table.add_column("UID")
    table.add_column("Name")
    table.add_column("Device Type")
    table.add_column("Software Version")
    table.add_column("Connectivity")
    table.add_column("Configuration")
    items = page.items or []
    for device in items:
        table.add_row(
            device.uid,
            device.name,
            device.device_type,
            device.software_version,
            device.connectivity_state,
            device.config_state,
        )
    console.print(table)


class DeviceListCommand(BaseCommand):
    """Reusable list command for a specific set of device types.

    Instantiate directly — no subclassing required::

        AsaListCommand = DeviceListCommand(
            console,
            entity_types=ASA_ENTITY_TYPES,
            spinner_text="Fetching ASA devices…",
            help_text="List ASA devices.",
        )
    """

    def __init__(
        self,
        console: Console,
        *,
        entity_types: Sequence[EntityType],
        spinner_text: str,
        help_text: str = "",
    ) -> None:
        super().__init__(console)
        self._entity_types = entity_types
        self._spinner_text = spinner_text
        self._help_text = help_text

    @property
    def name(self) -> str:
        return "list"

    @property
    def help_text(self) -> str:
        return self._help_text

    def build_params(self) -> Sequence[click.Parameter]:
        return inventory_list_params()

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        query = cast(str | None, kwargs.get("query"))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        inventory_service = InventoryService(config)

        device_type_filter = build_device_type_filter(self._entity_types)
        effective_query = f"({query}) AND {device_type_filter}" if query else device_type_filter

        silent = ctx.obj.get("silent", False) if ctx.obj else False

        def _fetch() -> DevicePage:
            return inventory_service.get_devices(
                limit=limit,
                offset=offset,
                query=effective_query,
            )

        if silent:
            page = _fetch()
        else:
            spinner = Spinner("dots", text=self._spinner_text)
            with Live(spinner, console=self.console, refresh_per_second=10, transient=True):
                page = _fetch()

        render_device_page(self.console, page, output_format, limit=limit, offset=offset)
