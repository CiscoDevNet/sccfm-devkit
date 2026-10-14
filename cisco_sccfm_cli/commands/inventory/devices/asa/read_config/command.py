# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click
from scc_firewall_manager_sdk import CdoTransaction

from cisco_sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    asa_check_option,
    asa_device_filter_params,
)
from cisco_sccfm_cli.commands.inventory.options import (
    config_path_option,
    format_option,
    timeout_option,
    wait_option,
)
from cisco_sccfm_cli.utils import print_json
from cisco_sccfm_core.services.inventory import AsaConfigReadService


class AsaReadConfigCommand(AsaDeviceTargetCommand):
    @property
    def name(self) -> str:
        return "read-config"

    @property
    def help_text(self) -> str:
        return (
            "Read the running configuration of ASA devices into SCC Firewall Manager. "
            "Use after changing a device outside SCC Firewall Manager (for example with "
            "'cli execute'). The read replaces SCC Firewall Manager's copy of the "
            "configuration, so changes staged there but not yet deployed can be lost."
        )

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *asa_device_filter_params(
                include_device_name=True,
                query_help_text="Filter devices to read by a Lucene query.",
                device_uids_help_text="List of device UIDs to read.",
            ),
            asa_check_option(),
            wait_option(),
            timeout_option(),
            format_option(),
            config_path_option(),
        ]

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        output_format = cast(str, kwargs.get("format"))
        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_asa_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=True,
        )

        if cast(bool, kwargs.get("check", False)):
            self.report_check_targets(
                targets, output_format=output_format, operation="configuration read"
            )
            return
        if not targets.device_uids:
            raise click.ClickException("No ASA devices matched the filter.")

        transaction = AsaConfigReadService(config=config).read_configuration(
            device_uids=targets.device_uids
        )
        transaction = self.wait_for_transaction(
            config=config,
            transaction=transaction,
            spinner_text="Reading ASA configuration..." if output_format != "json" else None,
            **kwargs,
        )
        self._render(
            transaction, device_count=len(targets.device_uids), output_format=output_format
        )

    def _render(
        self, transaction: CdoTransaction, *, device_count: int, output_format: str
    ) -> None:
        if self.is_failed_transaction(transaction):
            self.print_failed_transaction_details(cdo_transaction=transaction, format=output_format)
        if output_format == "json":
            print_json(transaction.to_dict())
            return
        self.console.print(
            f"[green]✓[/green] Configuration read for {device_count} device(s): "
            f"{transaction.cdo_transaction_status}"
        )
        self.console.print(f"[bold]Transaction UID:[/bold] {transaction.transaction_uid}")
