from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, cast

import click
from scc_firewall_manager_sdk import Device, DevicePage

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.options import limit_option, offset_option, query_option
from sccfm_cli.utils import print_json
from sccfm_core import CDFMC_MANAGED_FTD_DEVICE_TYPE_FILTER, InventoryService
from sccfm_core.types import ConfigLike

_DEFAULT_DEVICE_NAME_HELP = "Device name to search for (supports wildcards like 'branch-*')."
_DEFAULT_DEVICE_UIDS_HELP = "List of device UIDs to query."


def device_name_option(help_text: str = _DEFAULT_DEVICE_NAME_HELP) -> click.Option:
    return click.Option(["-n", "--device-name"], help=help_text)


def device_uids_option(help_text: str = _DEFAULT_DEVICE_UIDS_HELP) -> click.Option:
    return click.Option(
        ["-u", "--device-uids"],
        help=help_text,
        multiple=True,
        type=str,
    )


def ftd_check_option() -> click.Option:
    return click.Option(
        ["--check"],
        is_flag=True,
        default=False,
        help="Run a preflight check without performing the operation.",
    )


def ftd_device_filter_params(
    *,
    include_device_name: bool,
    query_help_text: str,
    device_uids_help_text: str = _DEFAULT_DEVICE_UIDS_HELP,
) -> list[click.Parameter]:
    params: list[click.Parameter] = []
    if include_device_name:
        params.append(device_name_option())
    params.extend(
        [
            query_option(help_text=query_help_text),
            limit_option(),
            offset_option(),
            device_uids_option(help_text=device_uids_help_text),
        ]
    )
    return params


@dataclass(frozen=True)
class FtdDeviceFilters:
    device_name: str | None
    query: str | None
    device_uids: tuple[str, ...] | None
    limit: int
    offset: int


@dataclass(frozen=True)
class FtdDeviceTargets:
    devices: list[Device]
    uid_to_device: dict[str, Device]
    device_uids: list[str]


class CdfmcFtdDeviceTargetCommand(BaseCommand):
    def _extract_ftd_device_filters(
        self,
        kwargs: Mapping[str, Any],
        *,
        include_device_name: bool,
    ) -> FtdDeviceFilters:
        device_name = cast(str | None, kwargs.get("device_name")) if include_device_name else None
        return FtdDeviceFilters(
            device_name=device_name,
            query=cast(str | None, kwargs.get("query")),
            device_uids=cast(tuple[str, ...] | None, kwargs.get("device_uids")),
            limit=cast(int, kwargs.get("limit")),
            offset=cast(int, kwargs.get("offset")),
        )

    def _validate_ftd_device_filters(
        self,
        ctx: click.Context,
        *,
        filters: FtdDeviceFilters,
        include_device_name: bool,
    ) -> None:
        selectors = [bool(filters.query), bool(filters.device_uids)]
        option_list = "--query or --device-uids"
        if include_device_name:
            selectors.insert(0, bool(filters.device_name))
            option_list = "--device-name, --query, or --device-uids"

        selected_count = sum(selectors)
        if selected_count == 0:
            ctx.fail(f"Provide one of: {option_list}.")
        if selected_count > 1:
            ctx.fail(f"Provide only one of: {option_list}.")

    def _query_with_ftd_device_type(self, query: str, *, wrap_query: bool) -> str:
        if wrap_query:
            return f"({query}) AND {CDFMC_MANAGED_FTD_DEVICE_TYPE_FILTER}"
        return f"{query} AND {CDFMC_MANAGED_FTD_DEVICE_TYPE_FILTER}"

    def _resolve_query(self, filters: FtdDeviceFilters) -> str | None:
        if filters.device_name:
            return f"name:{filters.device_name}"
        return filters.query

    def _get_ftd_devices(
        self,
        config: ConfigLike,
        *,
        filters: FtdDeviceFilters,
        wrap_query: bool,
    ) -> list[Device]:
        inventory_service = InventoryService(config=config)
        resolved_query = self._resolve_query(filters=filters)
        if resolved_query:
            page: DevicePage = inventory_service.get_devices(
                limit=filters.limit,
                offset=filters.offset,
                query=self._query_with_ftd_device_type(resolved_query, wrap_query=wrap_query),
            )
            return cast(list[Device], page.items or [])

        uid_query = " OR ".join([f"uid:{uid}" for uid in filters.device_uids or ()])
        page = inventory_service.get_devices(
            limit=filters.limit, offset=filters.offset, query=uid_query
        )
        return cast(list[Device], page.items or [])

    def resolve_ftd_targets_from_kwargs(
        self,
        *,
        ctx: click.Context,
        kwargs: Mapping[str, Any],
        config: ConfigLike,
        include_device_name: bool,
        wrap_query_with_parentheses: bool = False,
    ) -> FtdDeviceTargets:
        filters = self._extract_ftd_device_filters(
            kwargs=kwargs, include_device_name=include_device_name
        )
        self._validate_ftd_device_filters(
            ctx=ctx,
            filters=filters,
            include_device_name=include_device_name,
        )
        devices = self._get_ftd_devices(
            config=config,
            filters=filters,
            wrap_query=wrap_query_with_parentheses,
        )
        uid_to_device: dict[str, Device] = {device.uid: device for device in devices}
        device_uids = [device.uid for device in devices]

        return FtdDeviceTargets(
            devices=devices,
            uid_to_device=uid_to_device,
            device_uids=device_uids,
        )

    def report_check_targets(
        self,
        targets: FtdDeviceTargets,
        output_format: str = "table",
        operation: str = "operation",
    ) -> None:
        can_proceed = len(targets.devices) > 0
        reason = "targets_found" if can_proceed else "no_targets_matched"

        if output_format == "json":
            payload = [
                {
                    "name": d.name,
                    "uid": d.uid,
                    "device_type": d.device_type.value if d.device_type else None,
                }
                for d in targets.devices
            ]
            print_json(
                {
                    "operation": operation,
                    "can_proceed": can_proceed,
                    "reason": reason,
                    "matched_devices": len(targets.devices),
                    "devices": payload,
                }
            )
            return

        if not targets.devices:
            self.console.print(
                f"[yellow]![/yellow] No devices matched the filter; {operation} cannot proceed."
            )
            return

        self.console.print(
            f"[green]\u2713[/green] {len(targets.devices)} device(s) matched; "
            f"{operation} can proceed:"
        )
        for device in targets.devices:
            self.console.print(f"  - {device.name} (UID: {device.uid})")
