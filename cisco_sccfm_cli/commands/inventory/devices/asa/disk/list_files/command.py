# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table
from scc_firewall_manager_sdk import CdoTransaction, Device

from cisco_sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    asa_device_filter_params,
)
from cisco_sccfm_cli.commands.inventory.options import config_path_option, format_option
from cisco_sccfm_cli.utils import print_json, with_spinner
from cisco_sccfm_core import AsaDiskFileService
from cisco_sccfm_core.models.asa_disk_file import AsaDiskFile


class AsaDiskListFilesCommand(AsaDeviceTargetCommand):
    @property
    def name(self) -> str:
        return "list-files"

    @property
    def help_text(self) -> str:
        return "List OS, AnyConnect, and ASDM files on ASA device disks."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *asa_device_filter_params(
                include_device_name=True,
                query_help_text="Filter devices by a Lucene query.",
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Listing disk files...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        response_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_asa_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=True,
        )

        disk_file_service = AsaDiskFileService(config=config)
        results = disk_file_service.list_disk_files(device_uids=targets.device_uids)

        self._render_results(
            results=results,
            uid_to_device=targets.uid_to_device,
            format=response_format,
        )

    def _render_results(
        self,
        results: dict[str, list[AsaDiskFile]] | CdoTransaction,
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
        results: dict[str, list[AsaDiskFile]],
        uid_to_device: dict[str, Device],
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
        print_json(output)

    def _render_table(
        self,
        results: dict[str, list[AsaDiskFile]],
        uid_to_device: dict[str, Device],
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
