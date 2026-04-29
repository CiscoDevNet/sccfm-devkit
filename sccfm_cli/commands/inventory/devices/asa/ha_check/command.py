from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.table import Table
from scc_firewall_manager_sdk import CdoTransaction, Device

from sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    asa_device_filter_params,
)
from sccfm_cli.commands.inventory.options import config_path_option, format_option
from sccfm_cli.utils import print_json, with_spinner
from sccfm_core import AsaHaCheckReport, AsaHaCheckService


class AsaHaCheckCommand(AsaDeviceTargetCommand):
    """Run HA health checks on ASA failover devices."""

    @property
    def name(self) -> str:
        return "ha-check"

    @property
    def help_text(self) -> str:
        return (
            "Run HA health checks on ASA failover pairs. "
            "Verifies failover state, version parity, interface health, "
            "config sync, and unmonitored interfaces."
        )

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *asa_device_filter_params(
                include_device_name=True,
                query_help_text="Filter devices by a Lucene query.",
                device_uids_help_text="List of device UIDs to check.",
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Running HA health checks...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        response_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_asa_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=True,
        )

        devices = self.filter_online_devices(targets.devices)
        device_uids = [d.uid for d in devices]

        service = AsaHaCheckService(config=config)
        results = service.check_ha(device_uids=device_uids)

        self._render_results(
            results=results,
            uid_to_device=targets.uid_to_device,
            format=response_format,
        )

    # ── Rendering ────────────────────────────────────────────────

    def _render_results(
        self,
        results: dict[str, AsaHaCheckReport] | CdoTransaction,
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
        results: dict[str, AsaHaCheckReport],
        uid_to_device: dict[str, Device],
    ) -> None:
        output: list[dict[str, Any]] = []
        for device_uid, report in results.items():
            all_passed = all(c.passed for c in report.checks)
            output.append(
                {
                    "device_name": uid_to_device[device_uid].name,
                    "device_uid": device_uid,
                    "all_passed": all_passed,
                    "failover_unit": report.failover_status.failover_unit,
                    "this_host_state": report.failover_status.this_host.state,
                    "other_host_state": report.failover_status.other_host.state,
                    "checks": [
                        {
                            "name": c.name,
                            "passed": c.passed,
                            "detail": c.detail,
                        }
                        for c in report.checks
                    ],
                    "unmonitored_interfaces": [
                        {
                            "hardware_name": u.hardware_name,
                            "name": u.name,
                        }
                        for u in report.unmonitored_interfaces
                    ],
                }
            )
        print_json(output)

    def _render_table(
        self,
        results: dict[str, AsaHaCheckReport],
        uid_to_device: dict[str, Device],
    ) -> None:
        for device_uid, report in results.items():
            device_name = uid_to_device[device_uid].name
            all_passed = all(c.passed for c in report.checks)
            status_icon = "[green]✓[/green]" if all_passed else "[red]✗[/red]"
            fs = report.failover_status

            self.console.print(
                f"\n{status_icon} {device_name} " f"({fs.failover_unit} / {fs.this_host.state})"
            )

            table = Table(show_lines=True)
            table.add_column("Check")
            table.add_column("Status")
            table.add_column("Detail")

            for check in report.checks:
                icon = "[green]PASS[/green]" if check.passed else "[red]FAIL[/red]"
                table.add_row(check.name, icon, check.detail)

            self.console.print(table)

            if report.unmonitored_interfaces:
                self.console.print("[yellow]Unmonitored interfaces:[/yellow]")
                for u in report.unmonitored_interfaces:
                    self.console.print(f"  - {u.name} ({u.hardware_name})")
