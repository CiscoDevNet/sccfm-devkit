from __future__ import annotations

from typing import Any, Sequence, cast

import click
from scc_firewall_manager_sdk import DevicePage

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.devices.ftd.constants import FTD_ENTITY_TYPES
from sccfm_cli.commands.inventory.devices.rendering import render_device_page
from sccfm_cli.commands.inventory.options import inventory_list_params
from sccfm_cli.utils import with_spinner
from sccfm_core.services import InventoryService


class FtdListCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "list"

    @property
    def help_text(self) -> str:
        return (
            "List FTD devices (includes cdFMC-managed, FDM-managed, "
            "and on-prem FMC-managed FTDs)."
        )

    def build_params(self) -> Sequence[click.Parameter]:
        return inventory_list_params()

    @with_spinner("Fetching FTD devices from SCC Firewall Manager...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        query = cast(str | None, kwargs.get("query"))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        inventory_service = InventoryService(config)

        type_filter = " OR ".join(f"deviceType:{t.value}" for t in FTD_ENTITY_TYPES)
        device_type_filter = f"({type_filter})"
        effective_query = f"({query}) AND {device_type_filter}" if query else device_type_filter

        page: DevicePage = inventory_service.get_devices(
            limit=limit,
            offset=offset,
            query=effective_query,
        )

        render_device_page(self.console, page, output_format)
