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
from sccfm_core.services.inventory.asa_shun_service import AsaShunService, ShunEntrySpec


class AddShunCommand(AsaDeviceTargetCommand):
    """Add a shun entry on ASA devices."""

    @property
    def name(self) -> str:
        return "add"

    @property
    def help_text(self) -> str:
        return (
            "Shun (block) one or more source IP addresses on ASA devices. "
            "Each --source-ip can carry an inline connection tuple as: "
            "'<src_ip> [<dst_ip> [<src_port> [<dst_port> [<protocol>]]]]'. "
            "For a single entry, the tuple fields can also be passed as "
            "separate --dest-ip / --source-port / --dest-port / --protocol flags."
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
                multiple=True,
                type=str,
                help=(
                    "Source IP to block. Repeat to shun multiple IPs in one transaction. "
                    "Each value may embed a full connection tuple: "
                    "'<src_ip> [<dst_ip> [<src_port> [<dst_port> [<protocol>]]]]'."
                ),
            ),
            click.Option(
                ["--dest-ip"],
                required=False,
                type=str,
                default=None,
                help=(
                    "Destination IP of a specific connection to drop immediately. "
                    "Only valid when a single --source-ip is given without an inline tuple."
                ),
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
            asa_wait_option(),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Adding shun entries...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        source_ip_values = cast(tuple[str, ...], kwargs["source_ip"])
        dest_ip = cast(str | None, kwargs.get("dest_ip"))
        source_port = cast(int | None, kwargs.get("source_port"))
        dest_port = cast(int | None, kwargs.get("dest_port"))
        protocol = cast(str | None, kwargs.get("protocol"))
        check = cast(bool, kwargs.get("check", False))
        wait = cast(bool, kwargs.get("wait", False))
        response_format = cast(str, kwargs.get("format"))

        entries = self._build_entries(
            ctx=ctx,
            source_ip_values=source_ip_values,
            dest_ip=dest_ip,
            source_port=source_port,
            dest_port=dest_port,
            protocol=protocol,
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
        results: CdoTransaction | List[CdoCliResult] = service.add_shun_entries(
            device_uids=device_uids,
            entries=entries,
            wait=wait,
        )

        script = "\n".join(_build_display_script(e) for e in entries)

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

    @staticmethod
    def _build_entries(
        ctx: click.Context,
        *,
        source_ip_values: tuple[str, ...],
        dest_ip: str | None,
        source_port: int | None,
        dest_port: int | None,
        protocol: str | None,
    ) -> List[ShunEntrySpec]:
        has_separate_flags = any(p is not None for p in (dest_ip, source_port, dest_port, protocol))
        has_inline_tuple = any(" " in v for v in source_ip_values)

        if has_separate_flags and (len(source_ip_values) > 1 or has_inline_tuple):
            ctx.fail(
                "--dest-ip / --source-port / --dest-port / --protocol cannot be combined "
                "with multiple --source-ip values or an inline connection tuple."
            )

        if has_separate_flags:
            has_conn_params = any(p is not None for p in (source_port, dest_port, protocol))
            if has_conn_params and dest_ip is None:
                ctx.fail(
                    "--dest-ip is required when specifying --source-port, "
                    "--dest-port, or --protocol."
                )
            return [
                ShunEntrySpec(
                    source_ip=source_ip_values[0],
                    dest_ip=dest_ip,
                    source_port=source_port,
                    dest_port=dest_port,
                    protocol=protocol,
                )
            ]

        return [_parse_source_ip_value(ctx, v) for v in source_ip_values]


def _parse_source_ip_value(ctx: click.Context, value: str) -> ShunEntrySpec:
    """Parse an inline ``--source-ip`` value with an optional connection tuple.

    Accepted format: ``<src_ip> [<dst_ip> [<src_port> [<dst_port> [<protocol>]]]]``
    """
    parts = value.split()
    if len(parts) > 5:
        ctx.fail(
            f"Too many fields in --source-ip {value!r}. "
            "Expected: '<src_ip> [<dst_ip> [<src_port> [<dst_port> [<protocol>]]]]'."
        )
    source_ip = parts[0]
    dest_ip = parts[1] if len(parts) > 1 else None
    source_port: int | None = None
    dest_port: int | None = None
    protocol: str | None = None
    if len(parts) > 2:
        try:
            source_port = int(parts[2])
        except ValueError:
            ctx.fail(
                f"Invalid source_port {parts[2]!r} in --source-ip {value!r}: must be an integer."
            )
    if len(parts) > 3:
        try:
            dest_port = int(parts[3])
        except ValueError:
            ctx.fail(
                f"Invalid dest_port {parts[3]!r} in --source-ip {value!r}: must be an integer."
            )
    if len(parts) > 4:
        proto = parts[4].lower()
        if proto not in ("tcp", "udp"):
            ctx.fail(
                f"Invalid protocol {parts[4]!r} in --source-ip {value!r}: must be 'tcp' or 'udp'."
            )
        protocol = proto
    return ShunEntrySpec(
        source_ip=source_ip,
        dest_ip=dest_ip,
        source_port=source_port,
        dest_port=dest_port,
        protocol=protocol,
    )


def _build_display_script(entry: ShunEntrySpec) -> str:
    """Build a human-readable representation of a shun entry for display."""
    parts = ["shun", entry.source_ip]
    if entry.dest_ip is not None:
        parts.append(entry.dest_ip)
        parts.append(str(entry.source_port or 0))
        parts.append(str(entry.dest_port or 0))
        if entry.protocol is not None:
            parts.append(entry.protocol)
    return " ".join(parts)
