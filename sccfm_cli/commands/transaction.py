from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from rich.console import Console
from scc_firewall_manager_sdk import CdoTransaction

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.shared_options import (
    config_path_option,
    format_option,
    timeout_option,
    wait_option,
)
from sccfm_core.services.transaction_service import TransactionService


class TransactionCommand(BaseCommand):
    """Inspect transaction status by UID with optional polling."""

    def __init__(self, console: Console) -> None:
        super().__init__(console)

    @property
    def name(self) -> str:
        return "transaction"

    @property
    def help_text(self) -> str:
        return "Check transaction status by UID."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            click.Option(
                ["-t", "--transaction-uid"],
                required=True,
                help="Transaction UID to inspect.",
            ),
            wait_option(),
            timeout_option(default=3600),
            format_option(),
            config_path_option(),
        ]

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        config = self.get_profile(ctx=ctx, **kwargs)
        transaction_uid = cast(str, kwargs.get("transaction_uid"))
        output_format = cast(str, kwargs.get("format"))
        wait = cast(bool, kwargs.get("wait", False))

        service = TransactionService(config=config)
        # Fetch initial transaction to get details like polling URL.
        transaction = service.get_transaction(transaction_uid=transaction_uid)

        if wait:
            transaction = self.wait_for_transaction(
                config=config,
                transaction=transaction,
                spinner_text="Polling transaction status..." if output_format != "json" else None,
                **kwargs,
            )

        failed = self.is_failed_transaction(transaction)
        if output_format == "json":
            print(json.dumps(transaction.to_dict(), indent=2, ensure_ascii=False, default=str))
        elif not wait:
            # Only print details if we didn't wait (direct fetch).
            # For --wait, details were already printed during polling.
            self.console.print(f"[bold]Transaction UID:[/bold] {transaction.transaction_uid}")
            self.console.print(f"[bold]Status:[/bold] {transaction.cdo_transaction_status}")
            if transaction.transaction_polling_url:
                self.console.print(
                    f"[bold]Polling URL:[/bold] {transaction.transaction_polling_url}"
                )
            if transaction.error_message:
                self.console.print(f"[bold]Error:[/bold] {transaction.error_message}")
        else:
            # After waiting, just print final status and any error.
            self.console.print(f"  [bold]Status:[/bold] {transaction.cdo_transaction_status}")
            if transaction.error_message:
                self.console.print(f"  [bold]Error:[/bold] {transaction.error_message}")

        if wait and failed:
            ctx.exit(1)
