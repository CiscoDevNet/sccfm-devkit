from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Sequence, cast

import click
from rich.table import Table
from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction, Device, DevicePage

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.options import (
    config_path_option,
    format_option,
    limit_option,
    offset_option,
    query_option,
)
from sccfm_cli.utils.spinner import with_spinner
from sccfm_core import AsaCommandLineService, InventoryService
from sccfm_core.types import ConfigLike


def _normalize_output(result_text: str | None) -> list[str]:
    """Normalize raw CLI result text into a list of non-empty lines.

    - Converts literal ``\\t`` sequences to actual tabs.
    - Strips trailing whitespace from each line.
    - Removes empty lines.
    """
    if not result_text:
        return []
    output = result_text.replace("\\t", "\t")
    return [ln.rstrip() for ln in output.splitlines() if ln.strip()]


def _split_columns(text: str) -> list[str]:
    """Split a line on tabs or two-or-more consecutive spaces."""
    return re.split(r"\t+|\s{2,}", text.strip())


def _parse_cli_table(lines: list[str], max_columns: int = 6) -> tuple[list[str], list[list[str]]]:
    """Parse CLI output lines into headers and rows.

    The first line is treated as the header. Columns are split on tabs or
    two-or-more spaces. Header is trimmed to *max_columns*. Rows are padded
    or merged to match the header length.
    """
    if not lines:
        return ([], [])

    headers = [h.strip() for h in _split_columns(lines[0])[:max_columns]]

    rows: list[list[str]] = []
    for data_line in lines[1:]:
        cols = [c.strip() for c in _split_columns(data_line)]
        if len(cols) < len(headers):
            cols += [""] * (len(headers) - len(cols))
        elif len(cols) > len(headers):
            cols = cols[: len(headers) - 1] + [" ".join(cols[len(headers) - 1 :])]
        rows.append(cols[: len(headers)])

    return (headers, rows)


def _rows_to_dicts(headers: list[str], rows: list[list[str]]) -> list[dict[str, str]]:
    """Zip *headers* with each row to produce a list of dicts.

    Header names are lower-cased with hyphens/spaces replaced by underscores
    so they read naturally as JSON keys (e.g. ``"Lock-time"`` → ``"lock_time"``).
    """
    keys = [h.lower().replace("-", "_").replace(" ", "_") for h in headers]
    return [dict(zip(keys, row)) for row in rows]


class AsaListLocalUsersCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "list-local-users"

    @property
    def help_text(self) -> str:
        return "List local users on ASA devices."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            query_option(help_text="Filter devices by a Lucene query."),
            limit_option(),
            offset_option(),
            click.Option(
                ["-u", "--device-uids"],
                help="List of device UIDs to query.",
                multiple=True,
                type=str,
            ),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Getting list of local users for ASA devices...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        query = cast(str | None, kwargs.get("query"))
        device_uids_param = cast(tuple[str, ...] | None, kwargs.get("device_uids"))
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        response_format = cast(str, kwargs.get("format"))

        self._validate_filters(ctx, query=query, device_uids=device_uids_param)

        config = self.get_profile(ctx=ctx, **kwargs)
        devices = self._get_devices(
            config=config,
            query=query,
            device_uids=device_uids_param,
            limit=limit,
            offset=offset,
        )

        if not devices:
            self.console.print("No devices matched the given filter.")
            return

        devices = self.filter_online_devices(devices)
        uid_to_device: Dict[str, Device] = {device.uid: device for device in devices}
        device_uid_list: List[str] = [device.uid for device in devices]

        asa_cli_service = AsaCommandLineService(config=config)
        results: CdoTransaction | List[CdoCliResult] = asa_cli_service.execute_cli(
            device_uids=device_uid_list,
            asa_commands=["show aaa local user"],
        )

        self._render_results(
            results=results,
            uid_to_device=uid_to_device,
            format=response_format,
        )

    def _get_devices(
        self,
        config: ConfigLike,
        query: str | None,
        device_uids: tuple[str, ...] | None,
        limit: int,
        offset: int,
    ) -> List[Device]:
        inventory_service = InventoryService(config=config)
        if query:
            page: DevicePage = inventory_service.get_devices(
                limit=limit,
                offset=offset,
                query=f"{query} AND deviceType:ASA",
            )
            return cast(List[Device], page.items)

        q = " OR ".join([f"uid:{uid}" for uid in cast(tuple[str, ...], device_uids)])
        page = inventory_service.get_devices(limit=limit, offset=offset, query=q)
        return cast(List[Device], page.items)

    def _validate_filters(
        self,
        ctx: click.Context,
        *,
        query: str | None,
        device_uids: tuple[str, ...] | None,
    ) -> None:
        has_query = bool(query)
        has_uids = bool(device_uids)
        filter_count = sum([has_query, has_uids])

        if filter_count == 0:
            ctx.fail("Provide one of: --query or --device-uids.")
        if filter_count > 1:
            ctx.fail("Provide only one of: --query or --device-uids.")

    def _render_results(
        self,
        results: List[CdoCliResult] | CdoTransaction,
        uid_to_device: Dict[str, Device],
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
        results: List[CdoCliResult],
        uid_to_device: Dict[str, Device],
    ) -> None:
        grouped: dict[str, list[dict[str, str]]] = {}
        for item in results:
            device_name = uid_to_device[item.device_uid].name
            lines = _normalize_output(item.result)
            headers, rows = _parse_cli_table(lines, max_columns=6)
            grouped[device_name] = _rows_to_dicts(headers, rows)

        # Use print() to avoid Rich escape-sequence processing.
        print(json.dumps(grouped, indent=2, ensure_ascii=False))

    def _render_table(
        self,
        results: List[CdoCliResult],
        uid_to_device: Dict[str, Device],
    ) -> None:
        for item in results:
            device = uid_to_device[item.device_uid]
            lines = _normalize_output(item.result)

            if not lines:
                self.console.print(f"--- {device.name} ({item.device_uid}): no output ---")
                continue

            headers, rows = _parse_cli_table(lines, max_columns=6)

            table = Table(show_lines=False)
            table.add_column("Device Name")
            table.add_column("Device UID")
            for col in headers:
                table.add_column(col)
            for row in rows:
                table.add_row(device.name, item.device_uid, *row)

            self.console.print(table)
