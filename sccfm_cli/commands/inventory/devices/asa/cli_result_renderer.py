from __future__ import annotations

import json
from typing import Mapping, Sequence

from rich.console import Console
from rich.table import Table
from scc_firewall_manager_sdk import CdoCliResult, Device


def render_cli_results(
    *,
    console: Console,
    results: Sequence[CdoCliResult],
    uid_to_device: Mapping[str, Device],
    script: str,
    output_format: str,
) -> None:
    if output_format == "json":
        render_cli_results_json(results=results)
        return
    render_cli_results_table(
        console=console,
        results=results,
        uid_to_device=uid_to_device,
        script=script,
    )


def render_cli_results_json(*, results: Sequence[CdoCliResult]) -> None:
    results_data = [item.model_dump(mode="json") for item in results]
    json_output = json.dumps(results_data, indent=2, ensure_ascii=False)
    # Use print() instead of console.print() to avoid Rich processing escape sequences.
    print(json_output)


def render_cli_results_table(
    *,
    console: Console,
    results: Sequence[CdoCliResult],
    uid_to_device: Mapping[str, Device],
    script: str,
) -> None:
    console.print(f"Executed script: {script}")
    table = Table(show_lines=True)
    table.add_column("Name")
    table.add_column("UID")
    table.add_column("Result")
    table.add_column("Error Message")
    for item in results:
        table.add_row(
            uid_to_device[item.device_uid].name,
            item.device_uid,
            item.result,
            item.error_msg or "-",
        )

    console.print(table)
