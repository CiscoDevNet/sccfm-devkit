from __future__ import annotations

from typing import Any, List, Sequence, cast

import click
from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction

from sccfm_cli.commands.inventory.devices.asa.cli_result_renderer import render_cli_results
from sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    asa_check_option,
    asa_device_filter_params,
)
from sccfm_cli.commands.inventory.options import config_path_option, format_option
from sccfm_cli.utils import with_spinner
from sccfm_core.services.inventory.asa_shun_service import AsaShunService


class AddShunCommand(AsaDeviceTargetCommand):
    """Add a shun entry on ASA devices."""

    @property
    def name(self) -> str:
        return "add"

    @property
    def help_text(self) -> str:
        return (
            "Shun (block) a source IP address on ASA devices. "
            "Optionally specify a connection tuple to drop an existing connection immediately."
        )

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *asa_device_filter_params(
                include_device_name=True,
                query_help_text="Filter devices by a Lucene query.",
                device_uids_help_text="List of device UIDs to add the shun on.",
            ),
            click.Option(
                ["--source-ip"],
                required=True,
                type=str,
                help="The source IP address of the attacking host to block.",
            ),
            click.Option(
                ["--dest-ip"],
                required=False,
                type=str,
                default=None,
                help="Destination IP of a specific connection to drop immediately.",
            ),
            click.Option(
                ["--source-port"],
                required=False,
                type=int,
                default=None,
                help="Source port of the connection to drop (requires --dest-ip).",
            ),
            click.Option(
                ["--dest-port"],
                required=False,
                type=int,
                default=None,
                help="Destination port of the connection to drop (requires --dest-ip).",
            ),
            click.Option(
                ["--protocol"],
                required=False,
                type=click.Choice(["tcp", "udp"], case_sensitive=False),
                default=None,
                help="Protocol of the connection to drop (requires --dest-ip).",
            ),
            asa_check_option(),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Adding shun entry...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        source_ip = cast(str, kwargs["source_ip"])
        dest_ip = cast(str | None, kwargs.get("dest_ip"))
        source_port = cast(int | None, kwargs.get("source_port"))
        dest_port = cast(int | None, kwargs.get("dest_port"))
        protocol = cast(str | None, kwargs.get("protocol"))
        check = cast(bool, kwargs.get("check", False))
        response_format = cast(str, kwargs.get("format"))

        self._validate_connection_params(
            ctx, dest_ip=dest_ip, source_port=source_port, dest_port=dest_port, protocol=protocol
        )

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_asa_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=True,
        )

        if check:
            self.report_check_targets(targets, output_format=response_format, operation="shun add")
            return

        devices = self.filter_online_devices(targets.devices)
        device_uids = [d.uid for d in devices]

        service = AsaShunService(config=config)
        results: CdoTransaction | List[CdoCliResult] = service.add_shun(
            device_uids=device_uids,
            source_ip=source_ip,
            dest_ip=dest_ip,
            source_port=source_port,
            dest_port=dest_port,
            protocol=protocol,
        )

        if isinstance(results, CdoTransaction):
            self.print_failed_transaction_details(cdo_transaction=results, format=response_format)
            return

        render_cli_results(
            console=self.console,
            results=results,
            uid_to_device=targets.uid_to_device,
            script=f"shun {source_ip}",
            output_format=response_format,
        )

    @staticmethod
    def _validate_connection_params(
        ctx: click.Context,
        *,
        dest_ip: str | None,
        source_port: int | None,
        dest_port: int | None,
        protocol: str | None,
    ) -> None:
        has_conn_params = any(p is not None for p in (source_port, dest_port, protocol))
        if has_conn_params and dest_ip is None:
            ctx.fail(
                "--dest-ip is required when specifying --source-port, --dest-port, or --protocol."
            )
