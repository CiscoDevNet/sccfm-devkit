from typing import Any

import click
from rich.console import Console

from sccfm_cli.commands.base import BaseCommand


class AsaExecuteCliCommand(BaseCommand):
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        self.console.print("burak-crush-pineapple")

    def __init__(self, console: Console) -> None:
        super().__init__(console)

    @property
    def name(self) -> str:
        return "execute"

    @property
    def help_text(self) -> str:
        return "Execute CLI commands on ASA devices."
