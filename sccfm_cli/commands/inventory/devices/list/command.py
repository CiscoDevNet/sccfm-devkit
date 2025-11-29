from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence, cast

import click
from rich.table import Table
from scc_firewall_manager_sdk import DevicePage

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.options import inventory_list_params
from sccfm_cli.models import Config
from sccfm_cli.services import ConfigService
from sccfm_core.services import InventoryService


class DevicesListCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "list"

    @property
    def help_text(self) -> str:
        return "List devices."

    def build_params(self) -> Sequence[click.Parameter]:
        return inventory_list_params()

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        profile = ctx.obj["profile"]
        config_path = cast(Path | None, kwargs.get("config_path"))
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        query = cast(str, kwargs.get("query"))
        output_format = cast(str, kwargs.get("format"))

        config_service = ConfigService(path=config_path)
        config: Config | None = config_service.load(profile)
        if not config:
            warning = (
                f"[yellow]Profile '{profile}' not found. Run 'sccfm-cli --profile "
                f"{profile} configure'.[/yellow]"
            )
            self.console.print(warning)
            return

        inventory_service = InventoryService(config)
        page: DevicePage = inventory_service.get_devices(
            config=config,
            limit=limit,
            offset=offset,
            query=query,
        )
        self._render_page(page, output_format)

    def _render_page(self, page: DevicePage, output_format: str) -> None:
        if output_format == "json":
            items = page.items or []
            items_dict = [item.to_dict() for item in items]
            self.console.print(json.dumps(items_dict, indent=2, default=str))
            return

        self.console.print(f"Number of entries:  {page.count}")
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
        self.console.print(table)
