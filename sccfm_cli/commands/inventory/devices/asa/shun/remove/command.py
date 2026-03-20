from __future__ import annotations

from typing import Any, List, Sequence, cast

import click
from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction

from sccfm_cli.commands.inventory.devices.asa.cli_result_renderer import render_cli_results
from sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    asa_check_option,
    asa_device_filter_params,
    asa_wait_option,
)
from sccfm_cli.commands.inventory.options import config_path_option, format_option
from sccfm_cli.utils import with_spinner
from sccfm_core.services.inventory.asa_shun_service import AsaShunService


class RemoveShunCommand(AsaDeviceTargetCommand):
    """Remove a shun entry from ASA devices."""

    @property
    def name(self) -> str:
        return "remove"

    @property
    def help_text(self) -> str:
        return (
            "Remove one or more shun entries from ASA devices. "
            "Repeat --source-ip to remove multiple IPs in a single transaction."
        )

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *asa_device_filter_params(
                include_device_name=True,
                query_help_text="Filter devices by a Lucene query.",
                device_uids_help_text="List of device UIDs to remove the shun from.",
            ),
            click.Option(
                ["--source-ip"],
                required=True,
                multiple=True,
                type=str,
                help=(
                    "Source IP to remove from the shun list. "
                    "Repeat to remove multiple IPs in one transaction."
                ),
            ),
            asa_check_option(),
            asa_wait_option(),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Removing shun entries...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        source_ips = cast(tuple[str, ...], kwargs["source_ip"])
        check = cast(bool, kwargs.get("check", False))
        wait = cast(bool, kwargs.get("wait", False))
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
                operation="shun remove",
            )
            return

        devices = self.filter_online_devices(targets.devices)
        device_uids = [d.uid for d in devices]

        service = AsaShunService(config=config)
        results: CdoTransaction | List[CdoCliResult] = service.remove_shun_entries(
            device_uids=device_uids,
            source_ips=list(source_ips),
            wait=wait,
        )

        script = "\n".join(f"no shun {ip}" for ip in source_ips)

        if isinstance(results, CdoTransaction):
            if not wait:
                self.print_submitted_transaction(results, format=response_format)
            else:
                self.print_failed_transaction_details(
                    cdo_transaction=results, format=response_format
                )
            return

        render_cli_results(
            console=self.console,
            results=results,
            uid_to_device=targets.uid_to_device,
            script=script,
            output_format=response_format,
        )
