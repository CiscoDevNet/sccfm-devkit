# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Sequence

from rich.console import Console
from rich.table import Table

from sccfm_cli.utils import print_json
from sccfm_core.models.ftd_cli_result import FtdBulkCliResult


def render_ftd_cli_results(
    *,
    console: Console,
    result: FtdBulkCliResult,
    output_format: str,
) -> None:
    if output_format == "json":
        _render_json(result=result)
        return
    _render_table(console=console, result=result)


def _render_json(*, result: FtdBulkCliResult) -> None:
    payload = {
        "command": result.command,
        "device_responses": [
            {
                "device_uuid": r.device_uuid,
                "device_name": r.device_name,
                "response": r.response,
                "is_error": r.is_error,
                "error_msg": r.error_msg,
            }
            for r in result.device_responses
        ],
    }
    print_json(payload)


def _render_table(*, console: Console, result: FtdBulkCliResult) -> None:
    console.print(f"Command: {result.command}")
    table = Table(show_lines=True)
    table.add_column("Device Name")
    table.add_column("Device UUID")
    table.add_column("Output")
    table.add_column("Error")
    for r in result.device_responses:
        table.add_row(
            r.device_name,
            r.device_uuid,
            r.response or "-",
            r.error_msg or "-",
        )
    console.print(table)
