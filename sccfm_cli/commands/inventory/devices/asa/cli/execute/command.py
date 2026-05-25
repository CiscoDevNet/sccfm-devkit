# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence, cast

import click
from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction, Device

from sccfm_cli.commands.inventory.devices.asa.cli_result_renderer import (
    render_cli_results,
)
from sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    asa_check_option,
    asa_device_filter_params,
)
from sccfm_cli.commands.inventory.options import config_path_option, format_option
from sccfm_cli.utils import with_spinner
from sccfm_core import AsaCommandLineService


class AsaExecuteCliCommand(AsaDeviceTargetCommand):
    @property
    def name(self) -> str:
        return "execute"

    @property
    def help_text(self) -> str:
        return "Execute CLI commands on ASA devices."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *asa_device_filter_params(
                include_device_name=True,
                query_help_text="Filter devices to execute the CLI on by a Lucene query.",
                device_uids_help_text="List of device UIDs to execute the CLI on.",
            ),
            click.Option(
                ["-s", "--script"],
                help="ASA commands to execute, with each command separated by \\n.",
            ),
            click.Option(
                ["-f", "--script-file"],
                type=click.Path(path_type=Path, resolve_path=True),
                help=(
                    "Path to a file containing ASA commands to execute, with each command "
                    "separated by a newline."
                ),
            ),
            asa_check_option(),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Executing CLI commands...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        check = cast(bool, kwargs.get("check", False))
        response_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_asa_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=True,
        )

        if check:
            self.report_check_targets(
                targets,
                output_format=response_format,
                operation="CLI execution",
            )
            return

        script = cast(str | None, kwargs.get("script"))
        script_file = cast(Path | None, kwargs.get("script_file"))

        self._validate_script_filters(ctx=ctx, script=script, script_file=script_file)
        if script_file is not None:
            script = script_file.read_text()
        assert script is not None

        asa_cli_service = AsaCommandLineService(config=config)
        results: CdoTransaction | list[CdoCliResult] = asa_cli_service.execute_cli(
            device_uids=targets.device_uids,
            asa_commands=script.split("\n"),
        )
        self._render_results(
            results=results,
            uid_to_device=targets.uid_to_device,
            script=script,
            format=response_format,
        )

    def _render_results(
        self,
        results: list[CdoCliResult] | CdoTransaction,
        uid_to_device: dict[str, Device],
        script: str,
        format: str,
    ) -> None:
        if isinstance(results, CdoTransaction):
            self.print_failed_transaction_details(cdo_transaction=results, format=format)
            return

        render_cli_results(
            console=self.console,
            results=results,
            uid_to_device=uid_to_device,
            script=script,
            output_format=format,
        )

    def _validate_script_filters(
        self,
        ctx: click.Context,
        *,
        script: str | None,
        script_file: Path | None,
    ) -> None:
        has_script = bool(script)
        has_script_file = bool(script_file)
        if has_script == has_script_file:
            ctx.fail("Provide exactly one of --script or --script-file.")
