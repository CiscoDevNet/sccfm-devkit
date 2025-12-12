from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import click
from click_option_group import GroupedOption, OptionGroup
from rich.console import Console
from rich.table import Table

from sccfm_cli.commands.base import BaseCommand
from sccfm_core.services import HealthService


class StatusCommand(BaseCommand):
    def __init__(
        self,
        console: Console,
    ) -> None:
        super().__init__(console)

    @property
    def name(self) -> str:
        return "status"

    @property
    def help_text(self) -> str:
        return "Display the state of SCCFM subsystems."

    def build_params(self) -> Sequence[click.Parameter]:
        profile_group = OptionGroup("Profile", help="Profile storage overrides.")
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
        ]

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        profile = ctx.obj["profile"]
        config = self.get_profile(ctx=ctx, **kwargs)

        health_service = HealthService(config=config)
        table = Table(title=f"Health status for '{profile}'")
        table.add_column("Check", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")

        for status in health_service.check():
            icon = "[green]OK[/green]" if status.healthy else "[red]FAIL[/red]"
            table.add_row(status.name, icon, status.detail)

        masked_token = _mask_token(config.api_token)
        self.console.print(f"[bold]Region:[/bold] {config.region.upper()}")
        self.console.print(f"[bold]API token:[/bold] {masked_token}")
        self.console.print(table)


def _mask_token(token: str) -> str:
    if len(token) <= 4:
        return "*" * len(token)
    return "*" * (len(token) - 4) + token[-4:]
