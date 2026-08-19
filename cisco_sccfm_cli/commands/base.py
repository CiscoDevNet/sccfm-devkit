# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Sequence, cast

import click
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from scc_firewall_manager_sdk import ApiException, CdoTransaction, ConnectivityState, Device

from cisco_sccfm_cli.option_metadata import is_sensitive_option
from cisco_sccfm_cli.services import ConfigService
from cisco_sccfm_cli.utils import print_json, redact_data, redact_text
from cisco_sccfm_core import SccApiError
from cisco_sccfm_core.constants import DEFAULT_POLLING_INTERVAL_SEC, DEFAULT_TRANSACTION_TIMEOUT_SEC
from cisco_sccfm_core.models.cdo_transaction_status import CdoTransactionStatus
from cisco_sccfm_core.services.transaction_service import TransactionService
from cisco_sccfm_core.types import ConfigLike

_WINDOWS_SHELL = sys.platform == "win32"


def _join_shell_command(arguments: Sequence[str]) -> str:
    """Render arguments for the platform's default command shell."""
    if _WINDOWS_SHELL:
        return subprocess.list2cmdline(arguments)
    return shlex.join(arguments)


class BaseCommand(ABC):
    """Base class implementing the command pattern for CLI commands."""

    _SENSITIVE_VALUES_META_KEY = "sccfm_sensitive_values"

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
            setup_arguments = ["sccfm-cli", "--profile", profile, "configure"]
            if config_path is not None:
                setup_arguments.extend(["--config-path", str(config_path)])
            setup_command = _join_shell_command(setup_arguments)
            raise click.ClickException(
                f"Profile '{profile}' not found. Run this command to set it up:\n{setup_command}"
            )
        self._register_sensitive_value(ctx, config.api_token)
        return cast(ConfigLike, cast(object, config))

    def build_params(self) -> Sequence[click.Parameter]:
        return []

    def _dispatch(self, **kwargs: Any) -> None:
        ctx = click.get_current_context()
        self._register_sensitive_parameters(ctx, kwargs)
        exit_code: int | None = None
        click_exception: click.ClickException | None = None
        try:
            self.handle(ctx=ctx, **kwargs)
        except ApiException as e:
            sensitive_values = self._sensitive_values(ctx)
            output_format = cast(str | None, kwargs.get("format"))
            error = SccApiError.from_exception(e)

            if output_format == "json":
                print_json(redact_data(error.to_dict(), sensitive_values))
            else:
                self.console.print(
                    "[yellow]Error executing operation using the SCC Firewall Manager API. "
                    "If you think you should not be getting this error, please file a Github issue"
                    " with the details below.[/yellow]"
                )
                self.console.print(
                    f"[bold]Error message:[/bold] "
                    f"{redact_text(error.message, sensitive_values)}"
                )
                error_code = redact_text(str(error.error_code), sensitive_values)
                self.console.print(f"[bold]Error Code:[/bold] {error_code}")
                error_details = redact_data(error.details, sensitive_values)
                self.console.print(
                    f"[bold]Error Details:[/bold]\n{json.dumps(error_details, indent=2)}"
                )
            exit_code = -1
        except click.ClickException as exc:
            # Preserve Click's default error handling so usage/help is shown for user errors.
            exc.message = redact_text(str(exc.message), self._sensitive_values(ctx))
            exc.args = (exc.message,)
            exc.__context__ = None
            exc.__cause__ = None
            exc.__suppress_context__ = True
            exc.__traceback__ = None
            click_exception = exc
        except (click.Abort, click.exceptions.Exit):
            raise
        except KeyboardInterrupt:
            sys.exit(130)
        except Exception as e:
            message = redact_text(str(e), self._sensitive_values(ctx))
            self.console.print(f"[red]Error: {message}[/red]")
            exit_code = -1

        if click_exception is not None:
            raise click_exception
        if exit_code is not None:
            sys.exit(exit_code)

    def _register_sensitive_value(self, ctx: click.Context, value: str) -> None:
        """Register a secret for command-scoped output and exception redaction."""
        if not value:
            return
        values = self._sensitive_values(ctx)
        if value not in values:
            ctx.meta[self._SENSITIVE_VALUES_META_KEY] = (*values, value)

    def _register_sensitive_parameters(self, ctx: click.Context, kwargs: dict[str, Any]) -> None:
        """Register values from Click options explicitly marked as sensitive."""
        for parameter in ctx.command.params:
            if not isinstance(parameter, click.Option) or not is_sensitive_option(parameter):
                continue
            value = kwargs.get(parameter.name or "")
            if isinstance(value, str):
                self._register_sensitive_value(ctx, value)

    def _sensitive_values(self, ctx: click.Context) -> tuple[str, ...]:
        """Return secrets registered for the active Click command context."""
        raw_values = ctx.meta.get(self._SENSITIVE_VALUES_META_KEY, ())
        if not isinstance(raw_values, tuple):
            return ()
        return tuple(value for value in raw_values if isinstance(value, str) and value)

    def _prompt_sensitive(
        self,
        text: str,
        *,
        default: str | None = None,
        show_default: bool = True,
    ) -> str:
        """Prompt without echoing and immediately register the acquired secret."""
        value = cast(
            str,
            click.prompt(
                text,
                default=default,
                hide_input=True,
                show_default=show_default,
            ),
        )
        self._register_sensitive_value(click.get_current_context(), value)
        return value

    def _active_sensitive_values(
        self, sensitive_values: Sequence[str] | None = None
    ) -> Sequence[str]:
        """Resolve explicit secrets or inherit the active command registry."""
        if sensitive_values is not None:
            return sensitive_values
        ctx = click.get_current_context(silent=True)
        return self._sensitive_values(ctx) if ctx is not None else ()

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
        self,
        cdo_transaction: CdoTransaction,
        format: str = "table",
        *,
        sensitive_values: Sequence[str] | None = None,
    ) -> None:
        sensitive_values = self._active_sensitive_values(sensitive_values)
        if format == "json":
            print_json(redact_data(cdo_transaction.to_dict(), sensitive_values))
        else:
            transaction_uid = redact_text(str(cdo_transaction.transaction_uid), sensitive_values)
            transaction_status = redact_text(
                str(cdo_transaction.cdo_transaction_status), sensitive_values
            )
            error_message = redact_text(str(cdo_transaction.error_message), sensitive_values)
            transaction_details = redact_data(cdo_transaction.transaction_details, sensitive_values)
            self.console.print("[yellow]The execution failed. Transaction Details:[/yellow]")
            self.console.print("[bold]Transaction UID: [/bold]" f"{transaction_uid}")
            self.console.print("[bold]Transaction Status: [/bold]" f"{transaction_status}")
            self.console.print("[bold]Transaction Error Message: [/bold]" f"{error_message}")
            self.console.print(
                "[bold]Transaction Details: [/bold]\n" f"{json.dumps(transaction_details)}"
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
