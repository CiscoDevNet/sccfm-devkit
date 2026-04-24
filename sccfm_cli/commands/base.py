from __future__ import annotations

import json
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Sequence, cast

import click
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from scc_firewall_manager_sdk import ApiException, CdoTransaction, ConnectivityState, Device

from sccfm_cli.services import ConfigService
from sccfm_cli.utils import print_json
from sccfm_core import SccApiError
from sccfm_core.constants import DEFAULT_POLLING_INTERVAL_SEC, DEFAULT_TRANSACTION_TIMEOUT_SEC
from sccfm_core.models.cdo_transaction_status import CdoTransactionStatus
from sccfm_core.services.transaction_service import TransactionService
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
                print_json(error.to_dict())
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
        except KeyboardInterrupt:
            sys.exit(130)
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            sys.exit(-1)

    @abstractmethod
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        """Execute the command logic."""

    @property
    def console(self) -> Console:
        return self._console

    def filter_online_devices(self, devices: list[Device]) -> list[Device]:
        """Return only devices with ``ONLINE`` connectivity state.

        Prints a warning for each skipped device so the operator knows
        which devices were excluded.  Raises :class:`click.ClickException`
        if *no* devices are online.
        """
        online: list[Device] = []
        offline: list[Device] = []
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

    def wait_for_transaction(
        self,
        *,
        config: ConfigLike,
        transaction: CdoTransaction,
        polling_interval_sec: int = DEFAULT_POLLING_INTERVAL_SEC,
        spinner_text: str | None = None,
        **kwargs: Any,
    ) -> CdoTransaction:
        """Poll a transaction until it reaches a terminal state, printing status on each poll.

        Reads ``wait`` (default False) and ``timeout`` (default 3600) from
        *kwargs* so callers can forward CLI kwargs directly.
        Returns the original transaction unchanged when ``wait`` is False.

        When *spinner_text* is provided, a checkmark line is printed
        (e.g. ``\u2713 Triggering ASA upgrade\u2026``) and a live spinner
        shows the latest transaction status in-place.  All human-facing
        output is written to *stderr* so that stdout remains clean for
        machine-parseable formats like JSON.
        """
        wait = cast(bool, kwargs.get("wait", False))
        if not wait:
            return transaction
        if transaction.transaction_uid is None:
            raise click.ClickException("Transaction UID missing \u2014 cannot poll for status.")

        ctx = click.get_current_context()
        silent = (ctx.obj or {}).get("silent", False)

        stderr_console = Console(stderr=True)

        if spinner_text and not silent:
            stderr_console.print(f"[green]\u2713[/green] {spinner_text}")
            stderr_console.print(f"  [bold]Transaction UID:[/bold] {transaction.transaction_uid}")
            if transaction.transaction_polling_url:
                stderr_console.print(
                    f"  [bold]Polling URL:[/bold] {transaction.transaction_polling_url}"
                )

        timeout_sec = cast(int, kwargs.get("timeout", DEFAULT_TRANSACTION_TIMEOUT_SEC))
        service = TransactionService(config=config)

        if silent:
            return service.wait_for_transaction_to_finish(
                transaction_uid=transaction.transaction_uid,
                timeout_sec=timeout_sec,
                polling_interval_sec=polling_interval_sec,
            )

        spinner = Spinner("dots", text="Polling transaction status...")

        def _update_status(t: CdoTransaction) -> None:
            spinner.text = f"Status: {t.cdo_transaction_status}"

        with Live(spinner, console=stderr_console, refresh_per_second=10, transient=True):
            return service.wait_for_transaction_to_finish(
                transaction_uid=transaction.transaction_uid,
                timeout_sec=timeout_sec,
                polling_interval_sec=polling_interval_sec,
                on_poll=_update_status,
            )

    @staticmethod
    def is_failed_transaction(transaction: CdoTransaction) -> bool:
        """Return True if the transaction reached a terminal failure state."""
        return transaction.cdo_transaction_status in (
            CdoTransactionStatus.ERROR,
            CdoTransactionStatus.CANCELLED,
        )

    def print_failed_transaction_details(
        self, cdo_transaction: CdoTransaction, format: str = "table"
    ) -> None:
        if format == "json":
            print_json(cdo_transaction.to_dict())
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

    def print_submitted_transaction(
        self, cdo_transaction: CdoTransaction, format: str = "table"
    ) -> None:
        """Render a submitted (not-yet-completed) transaction."""
        if format == "json":
            print_json(cdo_transaction.to_dict())
        else:
            self.console.print("[green]✓[/green] Transaction submitted.")
            self.console.print(f"[bold]Transaction UID:[/bold] {cdo_transaction.transaction_uid}")
            self.console.print(f"[bold]Status:[/bold] {cdo_transaction.cdo_transaction_status}")
