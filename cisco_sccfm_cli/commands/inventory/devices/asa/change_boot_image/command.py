# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table
from scc_firewall_manager_sdk import CdoTransaction, ConfigState, ConnectivityState, Device

from cisco_sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    asa_check_option,
    asa_device_filter_params,
)
from cisco_sccfm_cli.commands.inventory.options import config_path_option, format_option
from cisco_sccfm_cli.utils import print_json, with_spinner
from cisco_sccfm_core.models.asa_boot_image_change_result import AsaBootImageChangeResult
from cisco_sccfm_core.services import AsaBootImageService
from cisco_sccfm_core.utils import validate_asa_image_path


class AsaChangeBootImageCommand(AsaDeviceTargetCommand):
    @property
    def name(self) -> str:
        return "change-boot-image"

    @property
    def help_text(self) -> str:
        return (
            "Change the configured ASA boot image for the next reload. "
            "The image must already exist on the device, and check mode validates "
            "the image path plus containing filesystem access."
        )

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *asa_device_filter_params(
                include_device_name=True,
                query_help_text="Filter devices by a Lucene query.",
            ),
            click.Option(
                ["--image-path"],
                required=True,
                help=(
                    "Full ASA image path already present on the device, for example "
                    "'disk0:/asa9xxx.bin' or 'boot:/asa9xxx.bin'."
                ),
            ),
            asa_check_option(),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Changing ASA boot image...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        response_format = cast(str, kwargs.get("format"))
        image_path = cast(str, kwargs["image_path"])
        check = cast(bool, kwargs.get("check", False))

        try:
            validate_asa_image_path(image_path)
        except ValueError as exc:
            ctx.fail(str(exc))

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_asa_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=True,
        )

        ready_devices: list[Device] = []
        not_ready_results: dict[str, AsaBootImageChangeResult] = {}
        for device in targets.devices:
            if _is_device_ready_for_config(device):
                ready_devices.append(device)
                continue

            connectivity = _state_text(
                _device_attr(device, "connectivity_state", "connectivityState")
            )
            config_state = _state_text(_device_attr(device, "config_state", "configState"))
            device_uid = device.uid
            assert device_uid is not None
            not_ready_results[device_uid] = AsaBootImageChangeResult(
                device_uid=device_uid,
                requested_image_path=image_path,
                status="device_not_ready",
                message=(
                    "Device is not ready for config mutation "
                    f"(connectivity_state={connectivity}, config_state={config_state})."
                ),
                boot_system_entries_before=[],
                boot_system_entries_after=[],
            )

        service_results: dict[str, AsaBootImageChangeResult] | CdoTransaction = {}
        if ready_devices:
            service = AsaBootImageService(config=config)
            ready_uids = [device.uid for device in ready_devices]
            service_results = (
                service.check_boot_image(device_uids=ready_uids, image_path=image_path)
                if check
                else service.change_boot_image(device_uids=ready_uids, image_path=image_path)
            )

        self._render_results(
            results=service_results,
            uid_to_device=targets.uid_to_device,
            format=response_format,
            supplemental_results=not_ready_results,
            ordered_uids=[device.uid for device in targets.devices],
        )

    def _render_results(
        self,
        *,
        results: dict[str, AsaBootImageChangeResult] | CdoTransaction,
        uid_to_device: dict[str, Device],
        format: str,
        supplemental_results: dict[str, AsaBootImageChangeResult],
        ordered_uids: list[str],
    ) -> None:
        if isinstance(results, CdoTransaction):
            self.print_failed_transaction_details(cdo_transaction=results, format=format)
            return

        merged: dict[str, AsaBootImageChangeResult] = {}
        for uid in ordered_uids:
            if uid in results:
                merged[uid] = results[uid]
            elif uid in supplemental_results:
                merged[uid] = supplemental_results[uid]

        if format == "json":
            self._render_json(results=merged, uid_to_device=uid_to_device)
        else:
            self._render_table(results=merged, uid_to_device=uid_to_device)

    def _render_json(
        self,
        *,
        results: dict[str, AsaBootImageChangeResult],
        uid_to_device: dict[str, Device],
    ) -> None:
        payload: list[dict[str, Any]] = []
        for device_uid, result in results.items():
            payload.append(
                {
                    "device_name": uid_to_device[device_uid].name,
                    "device_uid": device_uid,
                    "requested_image_path": result.requested_image_path,
                    "status": result.status,
                    "message": result.message,
                    "boot_system_entries_before": result.boot_system_entries_before,
                    "boot_system_entries_after": result.boot_system_entries_after,
                }
            )
        print_json(payload)

    def _render_table(
        self,
        *,
        results: dict[str, AsaBootImageChangeResult],
        uid_to_device: dict[str, Device],
    ) -> None:
        table = Table(show_lines=True)
        table.add_column("Device Name")
        table.add_column("Device UID")
        table.add_column("Requested Image")
        table.add_column("Status")
        table.add_column("Message")
        table.add_column("Boot Entries Before")
        table.add_column("Boot Entries After")

        for device_uid, result in results.items():
            table.add_row(
                uid_to_device[device_uid].name,
                device_uid,
                result.requested_image_path,
                self._colorize_status(result.status),
                result.message,
                _join_entries(result.boot_system_entries_before),
                _join_entries(result.boot_system_entries_after),
            )

        self.console.print(table)

    @staticmethod
    def _colorize_status(status: str) -> str:
        color_map = {
            "success": "[green]success[/green]",
            "would_change": "[yellow]would_change[/yellow]",
            "no_change": "[green]no_change[/green]",
            "image_not_found": "[red]image_not_found[/red]",
            "device_not_ready": "[yellow]device_not_ready[/yellow]",
            "failed": "[red]failed[/red]",
        }
        return color_map.get(status, status)


def _device_attr(device: Device, snake_name: str, camel_name: str) -> Any:
    return getattr(device, snake_name, getattr(device, camel_name, None))


def _state_text(state: Any) -> str:
    if state is None:
        return "unknown"
    return str(getattr(state, "value", state))


def _is_device_ready_for_config(device: Device) -> bool:
    connectivity = _state_text(_device_attr(device, "connectivity_state", "connectivityState"))
    config_state = _state_text(_device_attr(device, "config_state", "configState"))
    return (
        connectivity == ConnectivityState.ONLINE.value and config_state == ConfigState.SYNCED.value
    )


def _join_entries(entries: list[str]) -> str:
    return "\n".join(entries) if entries else "(none)"
