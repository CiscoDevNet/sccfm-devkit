from __future__ import annotations

import json
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Sequence, cast

import click
from rich.console import Console
from scc_firewall_manager_sdk import ApiException, CdoTransaction, ConnectivityState, Device

from sccfm_cli.services import ConfigService
from sccfm_core import SccApiError
from sccfm_core.types import ConfigLike


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

    def get_profile(self, ctx: click.Context, **kwargs: Any) -> ConfigLike:
        profile = ctx.obj["profile"]
        config_path = cast(Path | None, kwargs.get("config_path"))
        config_service = ConfigService(path=config_path)
        config = config_service.load(profile)
        if not config:
            raise click.ClickException(
                f"Profile '{profile}' not found. "
                f"Run 'sccfm-cli --profile {profile} configure' to set it up."
            )
        return cast(ConfigLike, cast(object, config))

    def build_params(self) -> Sequence[click.Parameter]:
        return []

    def _dispatch(self, **kwargs: Any) -> None:
        ctx = click.get_current_context()
        try:
            self.handle(ctx=ctx, **kwargs)
        except ApiException as e:
            output_format = cast(str | None, kwargs.get("format"))
            error = SccApiError.from_exception(e)

            if output_format == "json":
                self.console.print(json.dumps(json.loads(e.body or "{}"), indent=2))
            else:
                self.console.print(
                    "[yellow]Error executing operation using the SCC Firewall Manager API. "
                    "If you think you should not be getting this error, please file a Github issue"
                    " with the details below.[/yellow]"
                )
                self.console.print(f"[bold]Error message:[/bold] {error.message}")
                self.console.print(f"[bold]Error Code:[/bold] {error.error_code}")
                self.console.print(
                    f"[bold]Error Details:[/bold]\n{json.dumps(error.details, indent=2)}"
                )
            sys.exit(-1)
        except click.ClickException:
            # Preserve Click's default error handling so usage/help is shown for user errors.
            raise
        except (click.Abort, click.exceptions.Exit):
            raise
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            sys.exit(-1)

    @abstractmethod
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        """Execute the command logic."""

    @property
    def console(self) -> Console:
        return self._console

    def filter_online_devices(self, devices: List[Device]) -> List[Device]:
        """Return only devices with ``ONLINE`` connectivity state.

        Prints a warning for each skipped device so the operator knows
        which devices were excluded.  Raises :class:`click.ClickException`
        if *no* devices are online.
        """
        online: List[Device] = []
        offline: List[Device] = []
        for device in devices:
            if device.connectivity_state == ConnectivityState.ONLINE:
                online.append(device)
            else:
                offline.append(device)

        for device in offline:
            self.console.print(
                f"[yellow]Skipping '{device.name}' "
                f"(state: {device.connectivity_state}) "
                f"— CLI commands require ONLINE devices.[/yellow]"
            )

        if not online:
            raise click.ClickException(
                "No online devices found. CLI commands can only be "
                "executed on devices with connectivity state ONLINE."
            )
        return online

    def print_failed_transaction_details(
        self, cdo_transaction: CdoTransaction, format: str = "table"
    ) -> None:
        if format == "json":
            self.console.print(json.dumps(cdo_transaction.to_dict(), indent=2))
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
