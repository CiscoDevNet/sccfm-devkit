from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, cast

import click
from scc_firewall_manager_sdk import Device, DevicePage, EntityType

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.options import limit_option, offset_option, query_option
from sccfm_core import InventoryService
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


def asa_check_option() -> click.Option:
    """Reusable --check flag for ASA mutating commands."""
    return click.Option(
        ["--check"],
        is_flag=True,
        default=False,
        help="Run a preflight check without performing the operation.",
    )


def asa_device_filter_params(
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
class AsaDeviceFilters:
    device_name: str | None
    query: str | None
    device_uids: tuple[str, ...] | None
    limit: int
    offset: int


@dataclass(frozen=True)
class AsaDeviceTargets:
    devices: list[Device]
    uid_to_device: dict[str, Device]
    device_uids: list[str]


class AsaDeviceTargetCommand(BaseCommand):
    def _extract_asa_device_filters(
        self,
        kwargs: Mapping[str, Any],
        *,
        include_device_name: bool,
    ) -> AsaDeviceFilters:
        device_name = cast(str | None, kwargs.get("device_name")) if include_device_name else None
        return AsaDeviceFilters(
            device_name=device_name,
            query=cast(str | None, kwargs.get("query")),
            device_uids=cast(tuple[str, ...] | None, kwargs.get("device_uids")),
            limit=cast(int, kwargs.get("limit")),
            offset=cast(int, kwargs.get("offset")),
        )

    def _validate_asa_device_filters(
        self,
        ctx: click.Context,
        *,
        filters: AsaDeviceFilters,
        include_device_name: bool,
        require_exactly_one: bool = False,
        allow_no_filters: bool = False,
    ) -> None:
        selectors = [bool(filters.query), bool(filters.device_uids)]
        option_list = "--query or --device-uids"
        if include_device_name:
            selectors.insert(0, bool(filters.device_name))
            option_list = "--device-name, --query, or --device-uids"

        selected_count = sum(selectors)
        if require_exactly_one and selected_count != 1:
            ctx.fail(f"Provide exactly one of {option_list}.")
            return

        if selected_count == 0:
            if allow_no_filters:
                return
            ctx.fail(f"Provide one of: {option_list}.")
        if selected_count > 1:
            ctx.fail(f"Provide only one of: {option_list}.")

    def _query_with_asa_device_type(self, query: str, *, wrap_query: bool) -> str:
        if wrap_query:
            return f"({query}) AND deviceType:{EntityType.ASA.value}"
        return f"{query} AND deviceType:{EntityType.ASA.value}"

    def _resolve_query(self, filters: AsaDeviceFilters) -> str | None:
        if filters.device_name:
            return f"name:{filters.device_name}"
        return filters.query

    def _get_asa_devices(
        self,
        config: ConfigLike,
        *,
        filters: AsaDeviceFilters,
        wrap_query: bool,
    ) -> list[Device]:
        inventory_service = InventoryService(config=config)
        resolved_query = self._resolve_query(filters=filters)
        if resolved_query:
            page: DevicePage = inventory_service.get_devices(
                limit=filters.limit,
                offset=filters.offset,
                query=self._query_with_asa_device_type(resolved_query, wrap_query=wrap_query),
            )
            return cast(list[Device], page.items or [])

        if filters.device_uids:
            uid_query = " OR ".join([f"uid:{uid}" for uid in filters.device_uids])
            page = inventory_service.get_devices(
                limit=filters.limit, offset=filters.offset, query=uid_query
            )
            return cast(list[Device], page.items or [])

        page = inventory_service.get_devices(
            limit=filters.limit,
            offset=filters.offset,
            query=f"deviceType:{EntityType.ASA.value}",
        )
        return cast(list[Device], page.items or [])

    def resolve_asa_targets_from_kwargs(
        self,
        *,
        ctx: click.Context,
        kwargs: Mapping[str, Any],
        config: ConfigLike,
        include_device_name: bool,
        wrap_query_with_parentheses: bool = False,
        require_exactly_one_filter: bool = False,
        allow_no_filters: bool = False,
    ) -> AsaDeviceTargets:
        filters = self._extract_asa_device_filters(
            kwargs=kwargs, include_device_name=include_device_name
        )
        self._validate_asa_device_filters(
            ctx=ctx,
            filters=filters,
            include_device_name=include_device_name,
            require_exactly_one=require_exactly_one_filter,
            allow_no_filters=allow_no_filters,
        )
        devices = self._get_asa_devices(
            config=config,
            filters=filters,
            wrap_query=wrap_query_with_parentheses,
        )
        uid_to_device: dict[str, Device] = {device.uid: device for device in devices}
        device_uids = [device.uid for device in devices]

        return AsaDeviceTargets(
            devices=devices,
            uid_to_device=uid_to_device,
            device_uids=device_uids,
        )

    def report_check_targets(
        self,
        targets: AsaDeviceTargets,
        output_format: str = "table",
        operation: str = "operation",
    ) -> None:
        """Report matched device targets for ``--check`` mode."""
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
            self.console.print(
                json.dumps(
                    {
                        "operation": operation,
                        "can_proceed": can_proceed,
                        "reason": reason,
                        "matched_devices": len(targets.devices),
                        "devices": payload,
                    },
                    indent=2,
                )
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
