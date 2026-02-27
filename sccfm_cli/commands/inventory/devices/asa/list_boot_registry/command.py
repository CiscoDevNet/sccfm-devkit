from __future__ import annotations

import json
from typing import Any, Sequence, cast

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
from sccfm_core.models.asa_boot_registry import AsaBootRegistry
from sccfm_core.services.inventory.asa_boot_registry_service import AsaBootRegistryService
from sccfm_core.services.inventory.inventory_service import InventoryService
from sccfm_core.types import ConfigLike


class AsaListBootRegistryCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)

    @property
    def name(self) -> str:
        return "list-boot-registry"

    @property
    def help_text(self) -> str:
        return "Show boot registry info (system image, config register, boot entries) for ASAs."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            click.Option(
                ["-n", "--device-name"],
                help="Device name(s) to search for (supports wildcards like 'branch-*').",
                multiple=True,
                type=str,
            ),
            query_option(help_text="Filter devices by a Lucene query."),
            limit_option(),
            offset_option(),
            click.Option(
                ["-u", "--device-uid"],
                help="Device UID(s) to query.",
                multiple=True,
                type=str,
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Fetching boot registry info...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        device_names = cast(tuple[str, ...], kwargs.get("device_name", ()))
        query = cast(str | None, kwargs.get("query"))
        device_uids_param = cast(tuple[str, ...], kwargs.get("device_uid", ()))
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        response_format = cast(str, kwargs.get("format"))

        self._validate_filters(
            ctx,
            device_names=device_names,
            query=query,
            device_uids=device_uids_param,
        )

        config = self.get_profile(ctx=ctx, **kwargs)
        devices = self._get_devices(
            config=config,
            query=query,
            device_names=device_names,
            device_uids=device_uids_param,
            limit=limit,
            offset=offset,
        )
        devices = self.filter_online_devices(devices)
        uid_to_device: dict[str, Device] = {device.uid: device for device in devices}
        device_uids: list[str] = [device.uid for device in devices]

        service = AsaBootRegistryService(config=config)
        results = service.list_boot_registry(device_uids=device_uids)

        self._render_results(
            results=results,
            uid_to_device=uid_to_device,
            format=response_format,
        )

    # ── Rendering ────────────────────────────────────────────────

    def _render_results(
        self,
        results: dict[str, AsaBootRegistry] | CdoTransaction,
        uid_to_device: dict[str, Device],
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
        results: dict[str, AsaBootRegistry],
        uid_to_device: dict[str, Device],
    ) -> None:
        output: list[dict[str, Any]] = []
        for device_uid, boot in results.items():
            output.append(
                {
                    "device_name": uid_to_device[device_uid].name,
                    "device_uid": device_uid,
                    "system_image_file": boot.system_image_file,
                    "compiled_date": boot.compiled_date,
                    "config_register": boot.config_register,
                    "config_modified": boot.config_modified,
                    "boot_system_entries": boot.boot_system_entries,
                }
            )
        print(json.dumps(output, indent=2, ensure_ascii=False))

    def _render_table(
        self,
        results: dict[str, AsaBootRegistry],
        uid_to_device: dict[str, Device],
    ) -> None:
        table = Table(show_lines=True)
        table.add_column("Device Name")
        table.add_column("Device UID")
        table.add_column("System Image")
        table.add_column("Compiled")
        table.add_column("Config Register")
        table.add_column("Config Modified")
        table.add_column("Boot System Entries")

        for device_uid, boot in results.items():
            device_name = uid_to_device[device_uid].name
            table.add_row(
                device_name,
                device_uid,
                boot.system_image_file,
                boot.compiled_date,
                boot.config_register,
                "Yes" if boot.config_modified else "No",
                "\n".join(boot.boot_system_entries) if boot.boot_system_entries else "(none)",
            )
        self.console.print(table)

    # ── Device resolution ────────────────────────────────────────

    def _get_devices(
        self,
        config: ConfigLike,
        query: str | None,
        device_names: tuple[str, ...],
        device_uids: tuple[str, ...],
        limit: int,
        offset: int,
    ) -> list[Device]:
        inventory_service = InventoryService(config=config)

        if query:
            page: DevicePage = inventory_service.get_devices(
                limit=limit,
                offset=offset,
                query=f"{query} AND deviceType:ASA",
            )
            return cast(list[Device], page.items)

        # Build a combined query from names and/or UIDs.
        clauses: list[str] = []
        clauses.extend(f"name:{name}" for name in device_names)
        clauses.extend(f"uid:{uid}" for uid in device_uids)
        combined = " OR ".join(clauses)
        page = inventory_service.get_devices(
            limit=limit,
            offset=offset,
            query=f"({combined}) AND deviceType:ASA",
        )
        return cast(list[Device], page.items)

    def _validate_filters(
        self,
        ctx: click.Context,
        *,
        device_names: tuple[str, ...],
        query: str | None,
        device_uids: tuple[str, ...],
    ) -> None:
        has_names = bool(device_names)
        has_uids = bool(device_uids)
        has_query = bool(query)
        has_selectors = has_names or has_uids

        if not has_selectors and not has_query:
            ctx.fail("Provide at least one of: --device-name, --device-uid, or --query.")
        if has_query and has_selectors:
            ctx.fail("--query cannot be combined with --device-name or --device-uid.")
