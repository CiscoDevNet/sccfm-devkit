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
from sccfm_core import InventoryService
from sccfm_core.models.asa_password_change_result import AsaPasswordChangeResult
from sccfm_core.services.inventory.asa_user_password_service import (
    AsaUserPasswordService,
)
from sccfm_core.types import ConfigLike


class AsaChangePasswordCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)

    @property
    def name(self) -> str:
        return "change-password"

    @property
    def help_text(self) -> str:
        return "Change a local user password on ASA devices (with verification)."

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
                help="List of device UIDs to target.",
                multiple=True,
                type=str,
            ),
            click.Option(
                ["--username"],
                required=True,
                help="The local ASA username whose password will be changed.",
            ),
            click.Option(
                ["--password"],
                prompt=True,
                hide_input=True,
                help="The new password to set.",
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Changing password...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        device_name = cast(str | None, kwargs.get("device_name"))
        query = cast(str | None, kwargs.get("query"))
        device_uids_param = cast(tuple[str, ...] | None, kwargs.get("device_uids"))
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        username = cast(str, kwargs["username"])
        new_password = cast(str, kwargs["password"])
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

        password_service = AsaUserPasswordService(config=config)
        results = password_service.change_password(
            device_uids=device_uids,
            username=username,
            new_password=new_password,
        )

        self._render_results(
            results=results,
            uid_to_device=uid_to_device,
            format=response_format,
        )

    def _render_results(
        self,
        results: dict[str, AsaPasswordChangeResult] | CdoTransaction,
        uid_to_device: Dict[str, Device],
        format: str,
    ) -> None:
        if isinstance(results, CdoTransaction):
            self.print_failed_transaction_details(cdo_transaction=results, format=format)
            return

        if format == "json":
            self._render_json(results=results, uid_to_device=uid_to_device)
        else:
            self._render_table(results=results, uid_to_device=uid_to_device)

    def _render_json(
        self,
        results: dict[str, AsaPasswordChangeResult],
        uid_to_device: Dict[str, Device],
    ) -> None:
        output: list[dict[str, str]] = []
        for device_uid, result in results.items():
            device_name = uid_to_device[device_uid].name
            output.append(
                {
                    "device_name": device_name,
                    "device_uid": device_uid,
                    "status": result.status,
                    "message": result.message,
                }
            )
        print(json.dumps(output, indent=2, ensure_ascii=False))

    def _render_table(
        self,
        results: dict[str, AsaPasswordChangeResult],
        uid_to_device: Dict[str, Device],
    ) -> None:
        table = Table(show_lines=True)
        table.add_column("Device Name")
        table.add_column("Device UID")
        table.add_column("Status")
        table.add_column("Message")
        for device_uid, result in results.items():
            device_name = uid_to_device[device_uid].name
            status_display = self._colorize_status(result.status)
            table.add_row(
                device_name,
                device_uid,
                status_display,
                result.message,
            )
        self.console.print(table)

    @staticmethod
    def _colorize_status(status: str) -> str:
        color_map = {
            "success": "[green]success[/green]",
            "failed": "[red]failed[/red]",
            "user_not_found": "[red]user_not_found[/red]",
        }
        return color_map.get(status, status)

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
