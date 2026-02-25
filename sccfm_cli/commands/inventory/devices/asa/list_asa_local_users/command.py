from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from rich.table import Table
from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction, Device

from sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    asa_device_filter_params,
)
from sccfm_cli.commands.inventory.options import config_path_option, format_option
from sccfm_cli.utils.spinner import with_spinner
from sccfm_core import AsaCommandLineService
from sccfm_core.parsers import normalize_cli_output, parse_cli_table, rows_to_dicts


class AsaListLocalUsersCommand(AsaDeviceTargetCommand):
    @property
    def name(self) -> str:
        return "list-local-users"

    @property
    def help_text(self) -> str:
        return "List local users on ASA devices."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *asa_device_filter_params(
                include_device_name=False,
                query_help_text="Filter devices by a Lucene query.",
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Getting list of local users for ASA devices...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        response_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_asa_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=False,
        )

        if not targets.devices:
            self.console.print("No devices matched the given filter.")
            return

        asa_cli_service = AsaCommandLineService(config=config)
        results: CdoTransaction | list[CdoCliResult] = asa_cli_service.execute_cli(
            device_uids=targets.device_uids,
            asa_commands=["show aaa local user"],
        )

        self._render_results(
            results=results,
            uid_to_device=targets.uid_to_device,
            format=response_format,
        )

    def _render_results(
        self,
        results: list[CdoCliResult] | CdoTransaction,
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
        results: list[CdoCliResult],
        uid_to_device: dict[str, Device],
    ) -> None:
        grouped: dict[str, list[dict[str, str]]] = {}
        for item in results:
            device_name = uid_to_device[item.device_uid].name
            lines = normalize_cli_output(item.result)
            headers, rows = parse_cli_table(lines, max_columns=6)
            grouped[device_name] = rows_to_dicts(headers, rows)

        # Use print() to avoid Rich escape-sequence processing.
        print(json.dumps(grouped, indent=2, ensure_ascii=False))

    def _render_table(
        self,
        results: list[CdoCliResult],
        uid_to_device: dict[str, Device],
    ) -> None:
        for item in results:
            device = uid_to_device[item.device_uid]
            lines = normalize_cli_output(item.result)

            if not lines:
                self.console.print(f"--- {device.name} ({item.device_uid}): no output ---")
                continue

            headers, rows = parse_cli_table(lines, max_columns=6)

            table = Table(show_lines=False)
            table.add_column("Device Name")
            table.add_column("Device UID")
            for col in headers:
                table.add_column(col)
            for row in rows:
                table.add_row(device.name, item.device_uid, *row)

            self.console.print(table)
