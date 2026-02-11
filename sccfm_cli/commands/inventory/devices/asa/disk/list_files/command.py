from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence, cast

import click
from rich.console import Console
from rich.table import Table
from scc_firewall_manager_sdk import CdoTransaction, Device, DevicePage

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.options import (
    config_path_option,
    format_option,
    limit_option,
    offset_option,
    query_option,
)
from sccfm_cli.utils import with_spinner
from sccfm_core import AsaDiskFileService, InventoryService
from sccfm_core.models.asa_disk_file import AsaDiskFile
from sccfm_core.types import ConfigLike


class AsaDiskListFilesCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)

    @property
    def name(self) -> str:
        return "list-files"

    @property
    def help_text(self) -> str:
        return "List OS, AnyConnect, and ASDM files on ASA device disks."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            click.Option(
                ["-n", "--device-name"],
                help="Device name to search for (supports wildcards like 'branch-*').",
            ),
            query_option(help_text="Filter devices by a Lucene query."),
            limit_option(),
            offset_option(),
            click.Option(
                ["-u", "--device-uids"],
                help="List of device UIDs to query.",
                multiple=True,
                type=str,
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Listing disk files...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        device_name = cast(str | None, kwargs.get("device_name"))
        query = cast(str | None, kwargs.get("query"))
        device_uids_param = cast(tuple[str, ...] | None, kwargs.get("device_uids"))
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        response_format = cast(str, kwargs.get("format"))

        self._validate_filters(
            ctx,
            device_name=device_name,
            query=query,
            device_uids=device_uids_param,
        )

        if device_name:
            query = f"name:{device_name}"

        config = self.get_profile(ctx=ctx, **kwargs)
        devices = self._get_devices(
            config=config,
            query=query,
            device_uids=device_uids_param,
            limit=limit,
            offset=offset,
        )
        uid_to_device: Dict[str, Device] = {device.uid: device for device in devices}
        device_uids: List[str] = [device.uid for device in devices]

        disk_file_service = AsaDiskFileService(config=config)
        results = disk_file_service.list_disk_files(device_uids=device_uids)

        self._render_results(
            results=results,
            uid_to_device=uid_to_device,
            format=response_format,
        )

    def _render_results(
        self,
        results: dict[str, list[AsaDiskFile]] | CdoTransaction,
        uid_to_device: Dict[str, Device],
        format: str,
    ) -> None:
        if isinstance(results, CdoTransaction):
            self.print_failed_transaction_details(cdo_transaction=results, format="table")
            return

        if format == "json":
            self._render_json(results=results, uid_to_device=uid_to_device)
        else:
            self._render_table(results=results, uid_to_device=uid_to_device)

    def _render_json(
        self,
        results: dict[str, list[AsaDiskFile]],
        uid_to_device: Dict[str, Device],
    ) -> None:
        output: list[dict[str, Any]] = []
        for device_uid, files in results.items():
            device_name = uid_to_device[device_uid].name
            for f in files:
                output.append(
                    {
                        "device_name": device_name,
                        "device_uid": device_uid,
                        "file_name": f.name,
                        "size": f.size,
                        "date": f.date,
                        "file_type": f.file_type.value,
                    }
                )
        print(json.dumps(output, indent=2, ensure_ascii=False))

    def _render_table(
        self,
        results: dict[str, list[AsaDiskFile]],
        uid_to_device: Dict[str, Device],
    ) -> None:
        table = Table(show_lines=True)
        table.add_column("Device Name")
        table.add_column("Device UID")
        table.add_column("File Name")
        table.add_column("Size")
        table.add_column("Date")
        table.add_column("Type")
        for device_uid, files in results.items():
            device_name = uid_to_device[device_uid].name
            for f in files:
                table.add_row(
                    device_name,
                    device_uid,
                    f.name,
                    str(f.size),
                    f.date,
                    f.file_type.value,
                )
        self.console.print(table)

    def _get_devices(
        self,
        config: ConfigLike,
        query: str | None,
        device_uids: tuple[str, ...] | None,
        limit: int,
        offset: int,
    ) -> List[Device]:
        inventory_service = InventoryService(config=config)
        if query:
            page: DevicePage = inventory_service.get_devices(
                limit=limit,
                offset=offset,
                query=f"{query} AND deviceType:ASA",
            )
            return cast(List[Device], page.items)

        query = " OR ".join([f"uid:{uid}" for uid in cast(tuple[str, ...], device_uids)])
        page = inventory_service.get_devices(limit=limit, offset=offset, query=query)
        return cast(List[Device], page.items)

    def _validate_filters(
        self,
        ctx: click.Context,
        *,
        device_name: str | None,
        query: str | None,
        device_uids: tuple[str, ...] | None,
    ) -> None:
        has_device_name = bool(device_name)
        has_query = bool(query)
        has_uids = bool(device_uids)
        filter_count = sum([has_device_name, has_query, has_uids])

        if filter_count == 0:
            ctx.fail("Provide one of: --device-name, --query, or --device-uids.")
        if filter_count > 1:
            ctx.fail("Provide only one of: --device-name, --query, or --device-uids.")
