# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click

from cisco_sccfm_cli.commands.inventory.devices.cdfmc_managed_ftd.cli_result_renderer import (
    render_ftd_cli_results,
)
from cisco_sccfm_cli.commands.inventory.devices.cdfmc_managed_ftd.shared import (
    CdfmcFtdDeviceTargetCommand,
    ftd_check_option,
    ftd_device_filter_params,
)
from cisco_sccfm_cli.commands.inventory.options import config_path_option, format_option
from cisco_sccfm_cli.utils import with_spinner
from cisco_sccfm_core.models.ftd_cli_result import FtdBulkCliResult
from cisco_sccfm_core.services.inventory.ftd_cli_service import FtdCommandLineService


class FtdExecuteCliCommand(CdfmcFtdDeviceTargetCommand):
    @property
    def name(self) -> str:
        return "execute"

    @property
    def help_text(self) -> str:
        return (
            "Execute a show command on cdFMC-managed FTD devices. "
            "Only show commands are supported (e.g. show version, show failover)."
        )

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *ftd_device_filter_params(
                include_device_name=True,
                query_help_text="Filter FTD devices by a Lucene query.",
                device_uids_help_text="List of device UIDs to execute the command on.",
            ),
            click.Option(
                ["-c", "--command"],
                required=False,
                help="The show command to execute (e.g. 'show version').",
            ),
            ftd_check_option(),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Executing CLI command on FTD devices...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        check = cast(bool, kwargs.get("check", False))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_ftd_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=True,
        )

        if check:
            self.report_check_targets(
                targets,
                output_format=output_format,
                operation="FTD CLI execution",
            )
            return

        devices = self.filter_online_devices(targets.devices)
        command = cast(str | None, kwargs.get("command"))
        if not command:
            ctx.fail("--command is required.")

        ftd_cli_service = FtdCommandLineService(config=config)
        result: FtdBulkCliResult = ftd_cli_service.execute_cli(
            devices=devices,
            command=command,
        )

        render_ftd_cli_results(
            console=self.console,
            result=result,
            output_format=output_format,
        )
