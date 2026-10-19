# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Mapping, Sequence

from rich.console import Console
from rich.table import Table
from scc_firewall_manager_sdk import CdoCliResult, Device

from cisco_sccfm_cli.utils import print_json, redact_data, redact_text


def render_cli_results(
    *,
    console: Console,
    results: Sequence[CdoCliResult],
    uid_to_device: Mapping[str, Device],
    script: str,
    output_format: str,
    sensitive_values: Sequence[str] = (),
) -> None:
    if output_format == "json":
        render_cli_results_json(results=results, sensitive_values=sensitive_values)
        return
    render_cli_results_table(
        console=console,
        results=results,
        uid_to_device=uid_to_device,
        script=script,
        sensitive_values=sensitive_values,
    )


def render_cli_results_json(
    *, results: Sequence[CdoCliResult], sensitive_values: Sequence[str] = ()
) -> None:
    results_data = [item.model_dump(mode="json") for item in results]
    print_json(redact_data(results_data, sensitive_values))


def render_cli_results_table(
    *,
    console: Console,
    results: Sequence[CdoCliResult],
    uid_to_device: Mapping[str, Device],
    script: str,
    sensitive_values: Sequence[str] = (),
) -> None:
    console.print(f"Executed script: {redact_text(script, sensitive_values)}")
    table = Table(show_lines=True)
    table.add_column("Name")
    table.add_column("UID")
    table.add_column("Result")
    table.add_column("Error Message")
    for item in results:
        table.add_row(
            redact_text(uid_to_device[item.device_uid].name, sensitive_values),
            redact_text(item.device_uid, sensitive_values),
            redact_text(item.result or "-", sensitive_values),
            redact_text(item.error_msg or "-", sensitive_values),
        )

    console.print(table)
