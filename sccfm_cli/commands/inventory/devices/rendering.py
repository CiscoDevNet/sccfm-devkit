from __future__ import annotations

import json

from rich.console import Console
from rich.table import Table
from scc_firewall_manager_sdk import DevicePage


def render_device_page(console: Console, page: DevicePage, output_format: str) -> None:
    """Render a :class:`DevicePage` as JSON or a Rich table."""
    if output_format == "json":
        items = page.items or []
        items_dict = [item.to_dict() for item in items]
        console.print(json.dumps(items_dict, indent=2, default=str))
        return

    console.print(f"Number of entries:  {page.count}")
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
