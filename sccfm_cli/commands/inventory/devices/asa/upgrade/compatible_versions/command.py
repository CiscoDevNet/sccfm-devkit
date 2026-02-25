from __future__ import annotations

import json
from typing import Any, Dict, Sequence, cast

import click
from rich.table import Table
from scc_firewall_manager_sdk import (
    AsaCompatibleVersion,
    Device,
)

from sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    asa_device_filter_params,
)
from sccfm_cli.commands.inventory.options import config_path_option, format_option
from sccfm_cli.utils import with_spinner
from sccfm_core.models.asa_upgrade_version import AsaGroupCompatibleVersions
from sccfm_core.services.inventory import AsaUpgradeVersionService


class AsaUpgradeCompatibleVersionsCommand(AsaDeviceTargetCommand):
    @property
    def name(self) -> str:
        return "compatible-versions"

    @property
    def help_text(self) -> str:
        return "List software versions compatible with a group of ASA devices."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *asa_device_filter_params(
                include_device_name=True,
                query_help_text="Filter devices by a Lucene query.",
            ),
            click.Option(
                ["--per-device"],
                is_flag=True,
                default=False,
                help="Include per-device version breakdown in output.",
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Fetching compatible upgrade versions...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        response_format = cast(str, kwargs.get("format"))
        show_per_device = cast(bool, kwargs.get("per_device", False))

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_asa_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=True,
            wrap_query_with_parentheses=True,
        )

        upgrade_service = AsaUpgradeVersionService(config=config)
        results = upgrade_service.get_compatible_versions(device_uids=targets.device_uids)

        self._render_results(
            results=results,
            uid_to_device=targets.uid_to_device,
            format=response_format,
            show_per_device=show_per_device,
        )

    def _render_results(
        self,
        results: AsaGroupCompatibleVersions,
        uid_to_device: Dict[str, Device],
        format: str,
        show_per_device: bool,
    ) -> None:
        is_single = len(uid_to_device) == 1
        if format == "json":
            self._render_json(
                results=results,
                uid_to_device=uid_to_device,
                is_single=is_single,
                show_per_device=show_per_device,
            )
        else:
            self._render_table(
                results=results,
                uid_to_device=uid_to_device,
                is_single=is_single,
                show_per_device=show_per_device,
            )

    def _render_json(
        self,
        results: AsaGroupCompatibleVersions,
        uid_to_device: Dict[str, Device],
        is_single: bool,
        show_per_device: bool,
    ) -> None:
        if is_single and not show_per_device:
            uid = next(iter(uid_to_device))
            device = uid_to_device[uid]
            versions = results.per_device.get(uid, [])
            output: dict[str, Any] = {
                "device_name": device.name,
                "compatible_versions": [_version_to_dict(v) for v in versions],
            }
        else:
            device_count = len(uid_to_device)
            common = [_version_to_dict(v) for v in results.common_versions]
            output = {
                "device_count": device_count,
                "common_versions": common,
            }
            if show_per_device:
                per_device: dict[str, Any] = {}
                for uid, versions in results.per_device.items():
                    name = uid_to_device.get(uid, Device(name=uid, deviceType="ASA")).name
                    per_device[uid] = {
                        "device_name": name,
                        "compatible_versions": [_version_to_dict(v) for v in versions],
                    }
                output["per_device"] = per_device
        print(json.dumps(output, indent=2, ensure_ascii=False))

    def _render_table(
        self,
        results: AsaGroupCompatibleVersions,
        uid_to_device: Dict[str, Device],
        is_single: bool,
        show_per_device: bool,
    ) -> None:
        if is_single and not show_per_device:
            self._render_single_device_table(results, uid_to_device)
        else:
            self._render_group_table(results, uid_to_device, show_per_device)

    def _render_single_device_table(
        self,
        results: AsaGroupCompatibleVersions,
        uid_to_device: Dict[str, Device],
    ) -> None:
        uid = next(iter(uid_to_device))
        device = uid_to_device[uid]
        versions = results.per_device.get(uid, [])

        self.console.print(f"\n[bold]Compatible upgrade versions for {device.name}:[/bold]")

        if not versions:
            self.console.print("[yellow]No compatible versions found.[/yellow]")
            return

        table = Table(show_lines=True)
        table.add_column("Software Version")
        table.add_column("ASDM Version")
        for v in versions:
            table.add_row(
                v.software_version or "-",
                v.asdm_version or "-",
            )
        self.console.print(table)

    def _render_group_table(
        self,
        results: AsaGroupCompatibleVersions,
        uid_to_device: Dict[str, Device],
        show_per_device: bool,
    ) -> None:
        device_count = len(uid_to_device)
        self.console.print(
            f"\n[bold]Common compatible versions across {device_count} device(s):[/bold]"
        )

        if not results.common_versions:
            self.console.print("[yellow]No common compatible versions found.[/yellow]")
        else:
            table = Table(show_lines=True)
            table.add_column("Software Version")
            table.add_column("ASDM Version")
            for version in results.common_versions:
                table.add_row(
                    version.software_version or "-",
                    version.asdm_version or "-",
                )
            self.console.print(table)

        if show_per_device:
            for uid, versions in results.per_device.items():
                device = uid_to_device.get(uid, Device(name=uid, deviceType="ASA"))
                self.console.print(f"\n[bold]{device.name} ({uid}):[/bold]")
                if not versions:
                    self.console.print("[dim]  No compatible versions.[/dim]")
                    continue
                per_table = Table(show_lines=True)
                per_table.add_column("Software Version")
                per_table.add_column("ASDM Version")
                for v in versions:
                    per_table.add_row(
                        v.software_version or "-",
                        v.asdm_version or "-",
                    )
                self.console.print(per_table)


def _version_to_dict(v: AsaCompatibleVersion) -> dict[str, str | None]:
    return {
        "software_version": v.software_version,
        "asdm_version": v.asdm_version,
        "software_image_url": v.software_image_url,
        "asdm_image_url": v.asdm_image_url,
    }
