from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence, cast

import click
from rich.console import Console
from rich.table import Table
from scc_firewall_manager_sdk import CdoTransaction

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.utils.spinner import with_spinner
from sccfm_core import AsaCommandLineService, InventoryService


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


def _format_device_label(device_uid: str, device_name: str | None) -> str:
    """Return ``name (uid)`` when *device_name* is available, otherwise just *uid*."""
    if device_name:
        return f"{device_name} ({device_uid})"
    return device_uid


def _resolve_device_name(
    inventory_service: InventoryService | None,
    device_uid: str,
) -> str | None:
    """Best-effort lookup of a device name via the inventory service."""
    if inventory_service is None or not device_uid:
        return None
    try:
        device = inventory_service.get_device_by_uid(device_uid=device_uid)
        return getattr(device, "name", None) or None
    except Exception:
        return None


class AsaListLocalUsersCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "list-local-users"

    @property
    def help_text(self) -> str:
        return "List local users on an ASA device."

    @with_spinner("Getting list of local users for ASA device...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        uid = cast(str | None, kwargs.get("uid"))

        if not uid:
            ctx.fail("--uid is required")

        config = self.get_profile(ctx=ctx, **kwargs)

        asa_cli_service = AsaCommandLineService(config=config)
        results = asa_cli_service.execute_cli(
            device_uids=[uid], asa_commands=["show aaa local user"]
        )

        if isinstance(results, CdoTransaction):
            self.print_failed_transaction_details(cdo_transaction=results, format="table")
            return

        # Create the inventory service once for device-name lookups.
        inventory_service: InventoryService | None
        try:
            inventory_service = InventoryService(config=config)
        except Exception:
            inventory_service = None

        for item in results:
            result_text = getattr(item, "result", "") or ""
            device_uid = getattr(item, "device_uid", uid)
            device_name = _resolve_device_name(inventory_service, device_uid)
            device_label = _format_device_label(cast(str, device_uid), device_name)

            lines = _normalize_output(result_text)
            if not lines:
                self.console.print(f"--- CLI output for {device_label} ---")
                self.console.print("(no output)")
                continue

            headers, rows = _parse_cli_table(lines, max_columns=6)

            table = Table(show_lines=False)
            for col in headers:
                table.add_column(col)
            for row in rows:
                table.add_row(*row)

            self.console.print(f"--- Local users for {device_label} ---")
            self.console.print(table)

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            click.Option(
                ["--uid"],
                required=True,
                help="UID of the ASA device to list local users from.",
            ),
            click.Option(
                ["--config-path"],
                type=click.Path(path_type=Path, resolve_path=True),
                default=None,
                envvar="SCCFM_CONFIG",
                show_default=False,
                help=("Path to the configuration file " "(defaults to ~/.sccfm-cli/config.json)."),
            ),
        ]
