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
    asa_check_option,
    asa_device_filter_params,
)
from cisco_sccfm_cli.commands.inventory.options import config_path_option, format_option
from cisco_sccfm_cli.option_metadata import sensitive_option
from cisco_sccfm_cli.utils import print_json, redact_data, redact_text, with_spinner
from cisco_sccfm_core.models.asa_password_change_result import AsaPasswordChangeResult
from cisco_sccfm_core.services.inventory.asa_user_password_service import (
    AsaUserPasswordService,
)


class AsaChangePasswordCommand(AsaDeviceTargetCommand):
    @property
    def name(self) -> str:
        return "change-password"

    @property
    def help_text(self) -> str:
        return "Change a local user password on ASA devices (with verification)."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *asa_device_filter_params(
                include_device_name=True,
                query_help_text="Filter devices by a Lucene query.",
                device_uids_help_text="List of device UIDs to target.",
            ),
            click.Option(
                ["--username"],
                required=True,
                help="The local ASA username whose password will be changed.",
            ),
            sensitive_option(
                click.Option(
                    ["--new-password", "--password"],
                    required=False,
                    default=None,
                    hide_input=True,
                    help="The new password to set.",
                ),
            ),
            asa_check_option(),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Changing password...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        check = cast(bool, kwargs.get("check", False))
        response_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_asa_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=True,
        )

        if check:
            self.report_check_targets(
                targets,
                output_format=response_format,
                operation="password change",
            )
            return

        username = cast(str, kwargs["username"])
        new_password = cast(str | None, kwargs.get("new_password"))
        if not new_password:
            new_password = self._prompt_sensitive("Password")

        password_service = AsaUserPasswordService(config=config)
        results = password_service.change_password(
            device_uids=targets.device_uids,
            username=username,
            new_password=new_password,
        )

        self._render_results(
            results=results,
            uid_to_device=targets.uid_to_device,
            format=response_format,
        )

    def _render_results(
        self,
        results: dict[str, AsaPasswordChangeResult] | CdoTransaction,
        uid_to_device: dict[str, Device],
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
        uid_to_device: dict[str, Device],
    ) -> None:
        sensitive_values = self._active_sensitive_values()
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
        print_json(redact_data(output, sensitive_values))

    def _render_table(
        self,
        results: dict[str, AsaPasswordChangeResult],
        uid_to_device: dict[str, Device],
    ) -> None:
        table = Table(show_lines=True)
        table.add_column("Device Name")
        table.add_column("Device UID")
        table.add_column("Status")
        table.add_column("Message")
        sensitive_values = self._active_sensitive_values()
        for device_uid, result in results.items():
            device_name = uid_to_device[device_uid].name
            status_display = self._colorize_status(result.status)
            table.add_row(
                redact_text(device_name, sensitive_values),
                redact_text(device_uid, sensitive_values),
                redact_text(status_display, sensitive_values),
                redact_text(result.message, sensitive_values),
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
