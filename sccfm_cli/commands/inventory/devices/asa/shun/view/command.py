from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence, cast

import click
from rich.table import Table
from scc_firewall_manager_sdk import CdoTransaction, Device

from sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    asa_device_filter_params,
)
from sccfm_cli.commands.inventory.options import config_path_option, format_option
from sccfm_cli.utils import with_spinner
from sccfm_core.models.asa_shun_entry import AsaShunEntry, AsaShunInterfaceStats
from sccfm_core.services.inventory.asa_shun_service import AsaShunService


class ViewShunCommand(AsaDeviceTargetCommand):
    """View active shun entries on ASA devices."""

    @property
    def name(self) -> str:
        return "view"

    @property
    def help_text(self) -> str:
        return "Display active shun entries on ASA devices. Use --statistics for per-interface counters."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *asa_device_filter_params(
                include_device_name=True,
                query_help_text="Filter devices by a Lucene query.",
                device_uids_help_text="List of device UIDs to view shuns on.",
            ),
            click.Option(
                ["--statistics"],
                is_flag=True,
                default=False,
                help="Show per-interface shun statistics instead of shun entries.",
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Fetching shun info...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        statistics = cast(bool, kwargs.get("statistics", False))
        response_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_asa_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=True,
        )

        devices = self.filter_online_devices(targets.devices)
        device_uids = [d.uid for d in devices]

        service = AsaShunService(config=config)

        if statistics:
            results = service.view_shun_statistics(device_uids=device_uids)
            self._render_statistics(
                results=results,
                uid_to_device=targets.uid_to_device,
                format=response_format,
            )
        else:
            results = service.view_shun(device_uids=device_uids)
            self._render_entries(
                results=results,
                uid_to_device=targets.uid_to_device,
                format=response_format,
            )

    # ── Shun entries rendering ───────────────────────────────────

    def _render_entries(
        self,
        results: Dict[str, List[AsaShunEntry]] | CdoTransaction,
        uid_to_device: Dict[str, Device],
        format: str,
    ) -> None:
        if isinstance(results, CdoTransaction):
            self.print_failed_transaction_details(cdo_transaction=results, format="table")
            return

        if format == "json":
            self._render_entries_json(results=results, uid_to_device=uid_to_device)
        else:
            self._render_entries_table(results=results, uid_to_device=uid_to_device)

    def _render_entries_json(
        self,
        results: Dict[str, List[AsaShunEntry]],
        uid_to_device: Dict[str, Device],
    ) -> None:
        output: List[Dict[str, Any]] = []
        for device_uid, entries in results.items():
            output.append(
                {
                    "device_name": uid_to_device[device_uid].name,
                    "device_uid": device_uid,
                    "shun_entries": [
                        {
                            "interface": e.interface,
                            "source_ip": e.source_ip,
                            "destination_ip": e.destination_ip,
                            "source_port": e.source_port,
                            "destination_port": e.destination_port,
                            "protocol": e.protocol,
                        }
                        for e in entries
                    ],
                }
            )
        print(json.dumps(output, indent=2, ensure_ascii=False))

    def _render_entries_table(
        self,
        results: Dict[str, List[AsaShunEntry]],
        uid_to_device: Dict[str, Device],
    ) -> None:
        table = Table(title="Shun Entries", show_lines=True)
        table.add_column("Device Name")
        table.add_column("Device UID")
        table.add_column("Interface")
        table.add_column("Source IP")
        table.add_column("Destination IP")
        table.add_column("Src Port")
        table.add_column("Dst Port")
        table.add_column("Protocol")

        for device_uid, entries in results.items():
            device_name = uid_to_device[device_uid].name
            if not entries:
                table.add_row(device_name, device_uid, "(no shun entries)", "-", "-", "-", "-", "-")
                continue
            for entry in entries:
                table.add_row(
                    device_name,
                    device_uid,
                    entry.interface,
                    entry.source_ip,
                    entry.destination_ip,
                    str(entry.source_port),
                    str(entry.destination_port),
                    str(entry.protocol),
                )

        self.console.print(table)

    # ── Statistics rendering ─────────────────────────────────────

    def _render_statistics(
        self,
        results: Dict[str, List[AsaShunInterfaceStats]] | CdoTransaction,
        uid_to_device: Dict[str, Device],
        format: str,
    ) -> None:
        if isinstance(results, CdoTransaction):
            self.print_failed_transaction_details(cdo_transaction=results, format="table")
            return

        if format == "json":
            self._render_stats_json(results=results, uid_to_device=uid_to_device)
        else:
            self._render_stats_table(results=results, uid_to_device=uid_to_device)

    def _render_stats_json(
        self,
        results: Dict[str, List[AsaShunInterfaceStats]],
        uid_to_device: Dict[str, Device],
    ) -> None:
        output: List[Dict[str, Any]] = []
        for device_uid, stats in results.items():
            output.append(
                {
                    "device_name": uid_to_device[device_uid].name,
                    "device_uid": device_uid,
                    "interface_stats": [
                        {
                            "interface": s.interface,
                            "shunned": s.shunned,
                            "received": s.received,
                        }
                        for s in stats
                    ],
                }
            )
        print(json.dumps(output, indent=2, ensure_ascii=False))

    def _render_stats_table(
        self,
        results: Dict[str, List[AsaShunInterfaceStats]],
        uid_to_device: Dict[str, Device],
    ) -> None:
        table = Table(title="Shun Statistics", show_lines=True)
        table.add_column("Device Name")
        table.add_column("Device UID")
        table.add_column("Interface")
        table.add_column("Shunned")
        table.add_column("Received")

        for device_uid, stats in results.items():
            device_name = uid_to_device[device_uid].name
            if not stats:
                table.add_row(device_name, device_uid, "(no statistics)", "-", "-")
                continue
            for stat in stats:
                table.add_row(
                    device_name,
                    device_uid,
                    stat.interface,
                    str(stat.shunned),
                    str(stat.received),
                )

        self.console.print(table)
