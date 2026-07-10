# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Final, Sequence, cast

import click
from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction, Device

from cisco_sccfm_cli.commands.inventory.devices.asa.cli_result_renderer import (
    render_cli_results,
)
from cisco_sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    asa_check_option,
    asa_device_filter_params,
)
from cisco_sccfm_cli.commands.inventory.options import config_path_option, format_option
from cisco_sccfm_cli.utils import with_spinner
from cisco_sccfm_core import AsaCommandLineService


class SmartlicenseCommand(AsaDeviceTargetCommand):
    _ASAV_SMART_LICENSE_SCRIPT: Final[str] = (
        "license smart\n"
        "feature tier {feature_tier}\n"
        "throughput level {throughput_level}\n"
        "license smart register idtoken {token}\n"
        "write memory"
    )
    _HARDWARE_ASA_SMART_LICENSE_SCRIPT: Final[str] = (
        "license smart\n"
        "feature tier {feature_tier}\n"
        "license smart register idtoken {token}\n"
        "write memory"
    )

    @property
    def name(self) -> str:
        return "smartlicense"

    @property
    def help_text(self) -> str:
        return (
            "Apply Smart License using a Smart license token on ASA devices (the token must be"
            " valid and must have at least as many uses as there are devices)."
        )

    @with_spinner("Applying Smart Licenses...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        check = cast(bool, kwargs.get("check", False))
        response_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_asa_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=False,
            require_exactly_one_filter=True,
        )

        if check:
            self.report_check_targets(
                targets,
                output_format=response_format,
                operation="smartlicense",
            )
            return

        token = cast(str, kwargs.get("token"))
        feature_tier = cast(str, kwargs.get("feature_tier"))
        throughput_level = cast(str | None, kwargs.get("throughput_level"))

        if not token:
            ctx.fail("--token is required when not using --check.")
        if not feature_tier:
            ctx.fail("--feature-tier is required when not using --check.")

        self._validate_virtual_devices(
            ctx=ctx,
            devices=targets.devices,
            must_be_virtual=throughput_level is not None,
        )

        script_commands = self._build_script(feature_tier, throughput_level, token)

        asa_cli_service = AsaCommandLineService(config=config)
        results = asa_cli_service.execute_cli(
            device_uids=targets.device_uids,
            asa_commands=script_commands,
        )

        self._render_results(
            results=results,
            uid_to_device=targets.uid_to_device,
            script_text="\n".join(script_commands),
            format=response_format,
        )

    def _build_script(
        self, feature_tier: str, throughput_level: str | None, token: str
    ) -> list[str]:
        if throughput_level is not None:
            script = self._ASAV_SMART_LICENSE_SCRIPT.format(
                feature_tier=feature_tier, throughput_level=throughput_level, token=token
            )
        else:
            script = self._HARDWARE_ASA_SMART_LICENSE_SCRIPT.format(
                feature_tier=feature_tier, token=token
            )
        return script.split("\n")

    def _render_results(
        self,
        results: list[CdoCliResult] | CdoTransaction,
        uid_to_device: dict[str, Device],
        script_text: str,
        format: str,
    ) -> None:
        if isinstance(results, CdoTransaction):
            self.print_failed_transaction_details(cdo_transaction=results, format="table")
            return

        render_cli_results(
            console=self.console,
            results=results,
            uid_to_device=uid_to_device,
            script=script_text,
            output_format=format,
        )

    def _validate_virtual_devices(
        self,
        ctx: click.Context,
        *,
        devices: list[Device],
        must_be_virtual: bool,
    ) -> None:
        if must_be_virtual:
            non_virtual = [
                device
                for device in devices
                if not device.hardware_model or "ASAv" not in device.hardware_model
            ]
            if non_virtual:
                device_names = ", ".join([d.name for d in non_virtual])
                ctx.fail(
                    f"The following devices are not virtual ASAs: {device_names}. "
                    "If throughput level is specified, all of the ASAs selected have to be virtual"
                    " ASA devices."
                )

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *asa_device_filter_params(
                include_device_name=False,
                query_help_text="Filter devices to smart license by a Lucene query.",
                device_uids_help_text="List of device UIDs to apply smart license to.",
            ),
            asa_check_option(),
            format_option(),
            config_path_option(),
            click.Option(
                ["--token", "-t"],
                type=str,
                required=False,
                default=None,
                help="The smart license token for your virtual account, generated on "
                "https://software.cisco.com/clc",
            ),
            click.Option(
                ["--throughput-level"],
                type=click.Choice(["100M", "1G"], case_sensitive=True),
                required=False,
                help="The throughput level of your ASA (required only for virtual ASAs)",
            ),
            click.Option(
                ["--feature-tier"],
                type=click.Choice(["standard"], case_sensitive=True),
                required=False,
                default=None,
                help="The feature tier of your ASA",
            ),
        ]
