from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Sequence, cast

import click
from rich.table import Table
from scc_firewall_manager_sdk import Device

from sccfm_cli.commands.inventory.devices.ftd.shared import (
    FtdDeviceTargetCommand,
    ftd_device_filter_params,
)
from sccfm_cli.commands.inventory.options import config_path_option, format_option
from sccfm_cli.utils import with_spinner
from sccfm_core.services.inventory import FtdUpgradeVersionService

_VERSION_RE = re.compile(r"^\d+\.\d+")


@dataclass(frozen=True)
class _NotOnVersionDevice:
    device: Device
    recommended_version: str | None = None


class FtdListNotOnVersionCommand(FtdDeviceTargetCommand):
    @property
    def name(self) -> str:
        return "list-not-on-version"

    @property
    def help_text(self) -> str:
        return (
            "List FTD devices that are NOT running a specific or recommended software version. "
            "Use --version to specify a target version, or --recommended to check against "
            "the Cisco-suggested version for each device."
        )

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            click.Option(
                ["--version"],
                default=None,
                help=(
                    "Software version to check against (e.g. '7.4.1'). "
                    "Devices NOT on this version are listed. "
                    "Mutually exclusive with --recommended."
                ),
            ),
            click.Option(
                ["--recommended"],
                is_flag=True,
                default=False,
                help=(
                    "Check each device against its Cisco-recommended (suggested) version. "
                    "Mutually exclusive with --version."
                ),
            ),
            *ftd_device_filter_params(
                include_device_name=True,
                query_help_text=(
                    "Lucene query to narrow the device search "
                    "(combined with the version filter)."
                ),
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Fetching FTD devices...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        version = cast(str | None, kwargs.get("version"))
        recommended = cast(bool, kwargs.get("recommended", False))
        output_format = cast(str, kwargs.get("format"))

        self._validate_mode(ctx=ctx, version=version, recommended=recommended)

        has_filter = any(
            [
                kwargs.get("device_name"),
                kwargs.get("query"),
                kwargs.get("device_uids"),
            ]
        )

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_ftd_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=True,
            wrap_query_with_parentheses=True,
            allow_no_filters=True,
        )
        all_devices = targets.devices

        skipped: dict[str, str] = {}
        if recommended:
            not_on_version, skipped = self._check_recommended(
                config=config,
                devices=all_devices,
                uid_to_device=targets.uid_to_device,
            )
        else:
            assert version is not None
            not_on_version = [
                _NotOnVersionDevice(device=d) for d in all_devices if d.software_version != version
            ]

        self._render_results(
            not_on_version=not_on_version,
            version=version,
            recommended=recommended,
            output_format=output_format,
            matched_device_count=len(all_devices),
            has_filter=has_filter,
            skipped=skipped,
            uid_to_device=targets.uid_to_device,
        )

    @staticmethod
    def _validate_mode(ctx: click.Context, version: str | None, recommended: bool) -> None:
        if version and recommended:
            ctx.fail("Provide either --version or --recommended, not both.")
        if not version and not recommended:
            ctx.fail("Provide one of --version or --recommended.")
        if version and not _VERSION_RE.match(version):
            ctx.fail(
                f"Invalid version format: '{version}'. " "Expected format like '7.4.1' or '7.2.0'."
            )

    def _check_recommended(
        self,
        config: Any,
        devices: list[Device],
        uid_to_device: dict[str, Device],
    ) -> tuple[list[_NotOnVersionDevice], dict[str, str]]:
        device_uids = [d.uid for d in devices]
        if not device_uids:
            return [], {}

        upgrade_version_service = FtdUpgradeVersionService(config=config)
        results = upgrade_version_service.get_compatible_versions(device_uids=device_uids)

        not_on_version: list[_NotOnVersionDevice] = []
        skipped: dict[str, str] = {}

        for uid, reason in results.skipped.items():
            skipped[uid] = reason

        for device in devices:
            uid = device.uid or ""
            if uid in results.skipped:
                continue

            compatible = results.per_device.get(uid, [])
            suggested = next((v for v in compatible if v.is_suggested_version), None)

            if suggested is None:
                skipped[uid] = "No recommended version available"
                continue

            if device.software_version != suggested.software_version:
                not_on_version.append(
                    _NotOnVersionDevice(
                        device=device,
                        recommended_version=suggested.software_version,
                    )
                )

        return not_on_version, skipped

    # ── Rendering ────────────────────────────────────────────────────

    def _render_results(
        self,
        not_on_version: list[_NotOnVersionDevice],
        version: str | None,
        recommended: bool,
        output_format: str,
        matched_device_count: int,
        has_filter: bool,
        skipped: dict[str, str],
        uid_to_device: dict[str, Device],
    ) -> None:
        if output_format == "json":
            self._render_json(
                not_on_version=not_on_version,
                version=version,
                recommended=recommended,
                matched_device_count=matched_device_count,
                skipped=skipped,
            )
        else:
            self._render_table(
                not_on_version=not_on_version,
                version=version,
                recommended=recommended,
                matched_device_count=matched_device_count,
                has_filter=has_filter,
                skipped=skipped,
                uid_to_device=uid_to_device,
            )

    def _render_json(
        self,
        not_on_version: list[_NotOnVersionDevice],
        version: str | None,
        recommended: bool,
        matched_device_count: int,
        skipped: dict[str, str],
    ) -> None:
        output: dict[str, Any] = {
            "mode": "recommended" if recommended else "specified",
            "matched_device_count": matched_device_count,
            "device_count": len(not_on_version),
            "devices": [
                self._device_to_dict(entry, recommended=recommended) for entry in not_on_version
            ],
        }
        if version:
            output["version"] = version
        if recommended and skipped:
            output["skipped"] = skipped
        print(json.dumps(output, indent=2, ensure_ascii=False))

    def _render_table(
        self,
        not_on_version: list[_NotOnVersionDevice],
        version: str | None,
        recommended: bool,
        matched_device_count: int,
        has_filter: bool,
        skipped: dict[str, str],
        uid_to_device: dict[str, Device],
    ) -> None:
        version_label = "their recommended version" if recommended else f"version {version}"
        self.console.print(f"\n[bold]FTD devices NOT on {version_label}:[/bold]")

        if recommended and skipped:
            for uid, reason in skipped.items():
                device = uid_to_device.get(uid)
                name = device.name if device else None
                label = f"{name} ('{uid}')" if name else f"'{uid}'"
                self.console.print(f"[blue]i[/blue] [yellow]Skipped {label}: {reason}[/yellow]")

        if matched_device_count == 0:
            message = "No FTD devices matched the given filter."
            if not has_filter:
                message = "No FTD devices found."
            self.console.print(f"[yellow]![/yellow] {message}")
            return

        evaluated_count = matched_device_count - len(skipped)
        if not not_on_version:
            if evaluated_count == 0:
                self.console.print(
                    "[yellow]![/yellow] No matched device(s) could be evaluated "
                    "for recommended version compliance; all were skipped."
                )
                return
            self.console.print(
                f"[green]\u2713[/green] All {evaluated_count} evaluated device(s) "
                f"are on {version_label}."
            )
            return

        table = Table(show_lines=True)
        table.add_column("Name")
        table.add_column("UID")
        table.add_column("Software Version")
        if recommended:
            table.add_column("Recommended Version")
        table.add_column("Connectivity")
        table.add_column("Config State")

        for entry in not_on_version:
            d = entry.device
            row = [
                d.name or "-",
                d.uid or "-",
                d.software_version or "-",
            ]
            if recommended:
                row.append(entry.recommended_version or "-")
            row.extend(
                [
                    d.connectivity_state.value if d.connectivity_state else "-",
                    d.config_state.value if d.config_state else "-",
                ]
            )
            table.add_row(*row)

        self.console.print(table)
        self.console.print(
            f"\n[bold]{len(not_on_version)} of {evaluated_count} evaluated device(s) "
            f"are not on {version_label}.[/bold]"
        )

    @staticmethod
    def _device_to_dict(entry: _NotOnVersionDevice, *, recommended: bool) -> dict[str, Any]:
        d = entry.device
        result: dict[str, Any] = {
            "uid": d.uid,
            "name": d.name,
            "software_version": d.software_version,
            "connectivity_state": (d.connectivity_state.value if d.connectivity_state else None),
            "config_state": d.config_state.value if d.config_state else None,
        }
        if recommended:
            result["recommended_version"] = entry.recommended_version
        return result
