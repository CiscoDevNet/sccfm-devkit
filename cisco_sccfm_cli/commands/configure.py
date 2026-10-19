# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Final, Sequence, cast

import click
from click.core import ParameterSource
from click_option_group import GroupedOption, OptionGroup
from rich.console import Console

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.models import Config
from cisco_sccfm_cli.option_metadata import sensitive_option
from cisco_sccfm_cli.services import ConfigService
from cisco_sccfm_core.constants import SCCFM_REGION_CHOICES, SCCFM_REGIONS, normalize_sccfm_region


class ConfigureCommand(BaseCommand):
    _API_TOKEN_ENVVAR: Final[str] = "SCCFM_API_TOKEN"

    def __init__(
        self,
        console: Console,
        config_service: ConfigService | None = None,
    ) -> None:
        super().__init__(console)
        self._config_service = config_service

    @property
    def name(self) -> str:
        return "configure"

    @property
    def help_text(self) -> str:
        return "Configure API connectivity."

    def build_params(self) -> Sequence[click.Parameter]:
        profile_group = OptionGroup("Profile", help="Profile storage overrides.")
        credential_group = OptionGroup(
            "Credentials",
            help="Region and API token settings.",
        )
        return [
            GroupedOption(
                ["--config-path"],
                type=click.Path(path_type=Path, resolve_path=False),
                default=None,
                envvar="SCCFM_CONFIG",
                show_default=False,
                help=("Path to the configuration file " "(defaults to ~/.sccfm-cli/config.json)."),
                group=profile_group,
            ),
            GroupedOption(
                ["--region"],
                type=click.Choice(SCCFM_REGION_CHOICES, case_sensitive=False),
                help=f"SCCFM region ({', '.join(SCCFM_REGIONS)})",
                group=credential_group,
                required=True,
            ),
            sensitive_option(
                GroupedOption(
                    ["--api-token"],
                    type=str,
                    default=None,
                    envvar=self._API_TOKEN_ENVVAR,
                    show_envvar=True,
                    hide_input=True,
                    help=(
                        "API token for the chosen region. Passing it directly is supported for "
                        "compatibility but may expose it in process listings and shell history; "
                        f"prefer {self._API_TOKEN_ENVVAR} or the hidden prompt."
                    ),
                    group=credential_group,
                    required=False,
                ),
            ),
        ]

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        profile = ctx.obj["profile"]
        region = kwargs["region"]
        api_token = self._resolve_api_token(ctx=ctx, **kwargs)
        config_path = kwargs["config_path"]

        config_service = ConfigService(config_path)
        normalized_region = normalize_sccfm_region(region)
        assert normalized_region
        config = Config(profile=profile, region=normalized_region, api_token=api_token)
        config_service.save(config)
        self.console.print(f"[green]Profile '{profile}' updated[/green]")

    def _resolve_api_token(self, ctx: click.Context, **kwargs: Any) -> str:
        api_token = cast(str | None, kwargs.get("api_token"))
        source = ctx.get_parameter_source("api_token")

        if api_token is None:
            if not self._can_prompt():
                ctx.fail(
                    "An API token is required. Set "
                    f"{self._API_TOKEN_ENVVAR} or run interactively for a hidden prompt."
                )
            api_token = self._prompt_sensitive("API token")
        elif source is ParameterSource.COMMANDLINE:
            click.echo(
                "Warning: passing --api-token directly may expose it in process listings and "
                f"shell history; prefer {self._API_TOKEN_ENVVAR} or the hidden prompt.",
                err=True,
            )

        return self._validate_api_token(ctx=ctx, api_token=api_token)

    def _validate_api_token(self, ctx: click.Context, api_token: str) -> str:
        if not api_token.strip():
            ctx.fail("The API token cannot be empty.")
        return api_token

    def _can_prompt(self) -> bool:
        return sys.stdin.isatty()
