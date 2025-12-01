from __future__ import annotations

import json
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Sequence, cast

import click
from rich.console import Console
from scc_firewall_manager_sdk import ApiException, CdoTransaction

from sccfm_cli.models import Config
from sccfm_cli.services import ConfigService


class BaseCommand(ABC):
    """Base class implementing the command pattern for CLI commands."""

    def __init__(self, console: Console) -> None:
        self._console = console

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the Click command name."""

    @property
    def help_text(self) -> str:
        return ""

    def register(self, group: click.Group) -> None:
        group.add_command(self.build())

    def build(self) -> click.Command:
        return click.Command(
            name=self.name,
            help=self.help_text,
            callback=self._dispatch,
            params=list(self.build_params()),
        )

    def get_profile(self, ctx: click.Context, **kwargs: Any) -> Config | None:
        profile = ctx.obj["profile"]
        config_path = cast(Path | None, kwargs.get("config_path"))
        config_service = ConfigService(path=config_path)
        return config_service.load(profile)

    def build_params(self) -> Sequence[click.Parameter]:
        return []

    def _dispatch(self, **kwargs: Any) -> None:
        ctx = click.get_current_context()
        try:
            self.handle(ctx=ctx, **kwargs)
        except ApiException as e:
            output_format = cast(str | None, kwargs.get("format"))
            error = json.loads(e.body or "{}")

            if output_format == "json":
                self.console.print(json.dumps(error, indent=2))
            else:
                self.console.print(
                    "[yellow]Error executing operation using the SCC Firewall Manager API. "
                    "If you think you should not be getting this error, please file a Github issue"
                    " with the details below.[/yellow]"
                )
                self.console.print(f"[bold]Error message:[/bold] {error['errorMsg']}")
                self.console.print(f"[bold]Error Code:[/bold] {error['errorCode']}")
                self.console.print(
                    f"[bold]Error Details:[/bold]\n{json.dumps(error['details'], indent=2)}"
                )
                sys.exit(-1)
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            sys.exit(-1)

    @abstractmethod
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        """Execute the command logic."""

    @property
    def console(self) -> Console:
        return self._console

    def print_failed_transaction_details(
        self, cdo_transaction: CdoTransaction, format: str = "table"
    ) -> None:
        if format == "json":
            self.console.print(json.dumps(cdo_transaction, indent=2))
        else:
            self.console.print("[yellow]The execution failed. Transaction Details:[/yellow]")
            self.console.print(
                "[bold]Transaction UID: [/bold]" f"{cdo_transaction.transaction_uid}"
            )
            self.console.print(
                "[bold]Transaction Status: [/bold]" f"{cdo_transaction.cdo_transaction_status}"
            )
            self.console.print(
                "[bold]Transaction Error Message: [/bold]" f"{cdo_transaction.error_message}"
            )
            self.console.print(
                "[bold]Transaction Details: [/bold]\n"
                f"{json.dumps(cdo_transaction.transaction_details)}"
            )
        sys.exit(-1)
