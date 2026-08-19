# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Final, Mapping, Sequence, cast

import click
from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction, Device

from cisco_sccfm_cli.commands.inventory.devices.asa.cli_result_renderer import (
    render_cli_results,
)
from cisco_sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    AsaDeviceTargets,
    asa_check_option,
    asa_device_filter_params,
)
from cisco_sccfm_cli.commands.inventory.options import config_path_option, format_option
from cisco_sccfm_cli.option_metadata import sensitive_option
from cisco_sccfm_cli.utils import with_spinner
from cisco_sccfm_core import AsaCommandLineService
from cisco_sccfm_core.types import ConfigLike


class SmartlicenseCommand(AsaDeviceTargetCommand):
    _TOKEN_ENVVAR: Final[str] = "SCCFM_SMART_LICENSE_TOKEN"
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

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        check = cast(bool, kwargs.get("check", False))
        response_format = cast(str, kwargs.get("format"))
        self._validate_token_sources(ctx=ctx, **kwargs)

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self._resolve_targets(ctx=ctx, kwargs=kwargs, config=config)

        if check:
            self.report_check_targets(
                targets,
                output_format=response_format,
                operation="smartlicense",
            )
            return

        feature_tier = cast(str, kwargs.get("feature_tier"))
        throughput_level = cast(str | None, kwargs.get("throughput_level"))

        if not feature_tier:
            ctx.fail("--feature-tier is required when not using --check.")

        self._validate_virtual_devices(
            ctx=ctx,
            devices=targets.devices,
            must_be_virtual=throughput_level is not None,
        )

        token = self._resolve_token(ctx=ctx, **kwargs)
        script_commands = self._build_script(feature_tier, throughput_level, token)
        results = self._execute_cli(
            config=config,
            targets=targets,
            script_commands=script_commands,
        )

        self._render_results(
            results=results,
            uid_to_device=targets.uid_to_device,
            script_text="\n".join(script_commands),
            format=response_format,
            sensitive_values=(token,),
        )

    @with_spinner("Finding ASA devices...")
    def _resolve_targets(
        self,
        *,
        ctx: click.Context,
        kwargs: Mapping[str, Any],
        config: ConfigLike,
    ) -> AsaDeviceTargets:
        return self.resolve_asa_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=False,
            require_exactly_one_filter=True,
        )

    @with_spinner("Applying Smart Licenses...")
    def _execute_cli(
        self,
        *,
        config: ConfigLike,
        targets: AsaDeviceTargets,
        script_commands: list[str],
    ) -> list[CdoCliResult] | CdoTransaction:
        asa_cli_service = AsaCommandLineService(config=config)
        return asa_cli_service.execute_cli(
            device_uids=targets.device_uids,
            asa_commands=script_commands,
        )

    def _resolve_token(self, ctx: click.Context, **kwargs: Any) -> str:
        token = cast(str | None, kwargs.get("token"))
        token_file = cast(Path | None, kwargs.get("token_file"))

        if token_file is not None:
            token = self._read_token_file(ctx=ctx, token_file=token_file)
        elif token is None:
            if not self._can_prompt():
                ctx.fail(
                    "A Smart Licensing token is required. Set "
                    f"{self._TOKEN_ENVVAR}, use --token-file, or run interactively "
                    "for a hidden prompt."
                )
            token = self._prompt_sensitive("Smart Licensing token")

        self._register_sensitive_value(ctx, token)
        return self._validate_token(ctx=ctx, token=token)

    def _validate_token_sources(self, ctx: click.Context, **kwargs: Any) -> None:
        token = cast(str | None, kwargs.get("token"))
        token_file = cast(Path | None, kwargs.get("token_file"))
        if token is not None and token_file is not None:
            ctx.fail(
                "Use only one Smart Licensing token source: --token, "
                f"{self._TOKEN_ENVVAR}, or --token-file."
            )

    def _read_token_file(self, ctx: click.Context, token_file: Path) -> str:
        contents: str
        try:
            if token_file == Path("-"):
                contents = click.get_text_stream("stdin").read()
            else:
                contents = token_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            ctx.fail(f"Unable to read the Smart Licensing token from {token_file}.")

        return contents.rstrip("\r\n")

    def _validate_token(self, ctx: click.Context, token: str) -> str:
        if not token:
            ctx.fail("The Smart Licensing token cannot be empty.")
        if any(character.isspace() or not character.isprintable() for character in token):
            ctx.fail("The Smart Licensing token must be a single printable value without spaces.")
        return token

    def _can_prompt(self) -> bool:
        return sys.stdin.isatty()

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
        sensitive_values: tuple[str, ...],
    ) -> None:
        if isinstance(results, CdoTransaction):
            self.print_failed_transaction_details(
                cdo_transaction=results,
                format=format,
                sensitive_values=sensitive_values,
            )
            return

        render_cli_results(
            console=self.console,
            results=results,
            uid_to_device=uid_to_device,
            script=script_text,
            output_format=format,
            sensitive_values=sensitive_values,
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
            sensitive_option(
                click.Option(
                    ["--token", "-t"],
                    type=str,
                    required=False,
                    default=None,
                    envvar=self._TOKEN_ENVVAR,
                    show_envvar=True,
                    hide_input=True,
                    help=(
                        "Smart Licensing token for your virtual account. Passing it directly is "
                        "supported for compatibility but may expose it in process listings and "
                        f"shell history; prefer {self._TOKEN_ENVVAR}, --token-file, or the hidden "
                        "prompt."
                    ),
                ),
            ),
            click.Option(
                ["--token-file"],
                type=click.Path(
                    exists=True,
                    file_okay=True,
                    dir_okay=False,
                    readable=True,
                    resolve_path=True,
                    allow_dash=True,
                    path_type=Path,
                ),
                required=False,
                default=None,
                help="Read the Smart Licensing token from a file; use '-' to read from stdin.",
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
