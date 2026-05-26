# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import click
from click_option_group import GroupedOption, OptionGroup
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.models import Config
from sccfm_cli.services import ConfigService
from sccfm_core.constants import SCCFM_REGION_CHOICES, SCCFM_REGIONS, normalize_sccfm_region


class ConfigureCommand(BaseCommand):
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
                type=click.Path(path_type=Path, resolve_path=True),
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
            GroupedOption(
                ["--api-token"],
                help="API token for the chosen region",
                group=credential_group,
                required=True,
            ),
        ]

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        profile = ctx.obj["profile"]
        region = kwargs["region"]
        api_token = kwargs["api_token"]
        config_path = kwargs["config_path"]

        config_service = ConfigService(config_path)
        normalized_region = normalize_sccfm_region(region)
        assert normalized_region
        config = Config(profile=profile, region=normalized_region, api_token=api_token)
        config_service.save(config)
        self.console.print(f"[green]Profile '{profile}' updated[/green]")
