from __future__ import annotations

import re
from typing import Any, Sequence, cast

import click
from rich.table import Table
from scc_firewall_manager_sdk import Device

from sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    asa_device_filter_params,
)
from sccfm_cli.commands.inventory.options import config_path_option, format_option
from sccfm_cli.utils import print_json, with_spinner

_VERSION_RE = re.compile(r"^\d+\.\d+")


class AsaListNotOnVersionCommand(AsaDeviceTargetCommand):
    @property
    def name(self) -> str:
        return "list-not-on-version"

    @property
    def help_text(self) -> str:
        return (
            "List ASA devices that are NOT running a specific software version. "
            "Useful for identifying devices that still need upgrading to a target version."
        )

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            click.Option(
                ["--version"],
                required=True,
                help="Software version to exclude (e.g. '9.20(3)13'). Devices NOT on this version are listed.",
            ),
            *asa_device_filter_params(
                include_device_name=True,
                query_help_text=(
                    "Lucene query to narrow the device search "
                    "(combined with the version exclusion filter)."
                ),
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Fetching ASA devices not on specified version...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        version = cast(str, kwargs.get("version"))
        output_format = cast(str, kwargs.get("format"))
        has_filter = any(
            [
                kwargs.get("device_name"),
                kwargs.get("query"),
                kwargs.get("device_uids"),
            ]
        )

        self._validate_version_format(ctx=ctx, version=version)

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_asa_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=True,
            wrap_query_with_parentheses=True,
            allow_no_filters=True,
        )
        all_devices = targets.devices

        # Filter client-side: exclude devices already on the target version
        devices = [d for d in all_devices if d.software_version != version]

        self._render_results(
            devices=devices,
            version=version,
            output_format=output_format,
            matched_device_count=len(all_devices),
            has_filter=has_filter,
        )

    @staticmethod
    def _validate_version_format(ctx: click.Context, version: str) -> None:
        if not _VERSION_RE.match(version):
            ctx.fail(
                f"Invalid version format: '{version}'. "
                "Expected Cisco format like '9.20(3)13' or '9.18.4'."
            )

    def _render_results(
        self,
        devices: list[Device],
        version: str,
        output_format: str,
        matched_device_count: int,
        has_filter: bool,
    ) -> None:
        if output_format == "json":
            self._render_json(
                devices=devices,
                version=version,
                matched_device_count=matched_device_count,
            )
        else:
            self._render_table(
                devices=devices,
                version=version,
                matched_device_count=matched_device_count,
                has_filter=has_filter,
            )

    def _render_json(
        self,
        devices: list[Device],
        version: str,
        matched_device_count: int,
    ) -> None:
        output = {
            "version": version,
            "matched_device_count": matched_device_count,
            "device_count": len(devices),
            "devices": [
                {
                    "uid": d.uid,
                    "name": d.name,
                    "software_version": d.software_version,
                    "asdm_version": d.asdm_version,
                    "connectivity_state": (
                        d.connectivity_state.value if d.connectivity_state else None
                    ),
                    "config_state": d.config_state.value if d.config_state else None,
                }
                for d in devices
            ],
        }
        print_json(output)

    def _render_table(
        self,
        devices: list[Device],
        version: str,
        matched_device_count: int,
        has_filter: bool,
    ) -> None:
        self.console.print(f"\n[bold]ASA devices NOT on version {version}:[/bold]")

        if matched_device_count == 0:
            message = "No ASA devices matched the given filter."
            if not has_filter:
                message = "No ASA devices found."
            self.console.print(f"[yellow]![/yellow] {message}")
            return

        if not devices:
            self.console.print(
                f"[green]\u2713[/green] All {matched_device_count} matched device(s) are on version {version}."
            )
            return

        table = Table(show_lines=True)
        table.add_column("Name")
        table.add_column("UID")
        table.add_column("Software Version")
        table.add_column("ASDM Version")
        table.add_column("Connectivity")
        table.add_column("Config State")

        for d in devices:
            table.add_row(
                d.name or "-",
                d.uid or "-",
                d.software_version or "-",
                d.asdm_version or "-",
                d.connectivity_state.value if d.connectivity_state else "-",
                d.config_state.value if d.config_state else "-",
            )

        self.console.print(table)
        self.console.print(
            f"\n[bold]{len(devices)} of {matched_device_count} matched device(s) are not on version {version}.[/bold]"
        )
