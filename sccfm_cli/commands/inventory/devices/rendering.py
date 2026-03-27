from __future__ import annotations

import json
import math
from abc import abstractmethod
from typing import Any, Sequence, cast

import click
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from scc_firewall_manager_sdk import DevicePage, EntityType

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.options import inventory_list_params
from sccfm_core.services import InventoryService


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
        console.print(json.dumps(items_dict, indent=2, default=str))
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


def _build_device_type_filter(entity_types: Sequence[EntityType]) -> str:
    """Build a Lucene device-type filter from one or more entity types."""
    if len(entity_types) == 1:
        return f"deviceType:{entity_types[0].value}"
    clause = " OR ".join(f"deviceType:{t.value}" for t in entity_types)
    return f"({clause})"


class DeviceListCommand(BaseCommand):
    """Base class for device-type-scoped list commands.

    Subclasses only need to define :attr:`entity_types`,
    :attr:`help_text`, and :attr:`spinner_text`.
    """

    @property
    def name(self) -> str:
        return "list"

    @property
    @abstractmethod
    def entity_types(self) -> Sequence[EntityType]:
        """Device types to filter on."""

    @property
    @abstractmethod
    def spinner_text(self) -> str:
        """Spinner message shown while fetching."""

    def build_params(self) -> Sequence[click.Parameter]:
        return inventory_list_params()

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        query = cast(str | None, kwargs.get("query"))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        inventory_service = InventoryService(config)

        device_type_filter = _build_device_type_filter(self.entity_types)
        effective_query = (
            f"({query}) AND {device_type_filter}" if query else device_type_filter
        )

        silent = ctx.obj.get("silent", False) if ctx.obj else False

        def _fetch() -> DevicePage:
            return inventory_service.get_devices(
                limit=limit, offset=offset, query=effective_query,
            )

        if silent:
            page = _fetch()
        else:
            spinner = Spinner("dots", text=self.spinner_text)
            with Live(spinner, console=self.console, refresh_per_second=10, transient=True):
                page = _fetch()

        render_device_page(self.console, page, output_format, limit=limit, offset=offset)
