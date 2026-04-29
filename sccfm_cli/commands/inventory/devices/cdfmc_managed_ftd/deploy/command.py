from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.live import Live
from rich.spinner import Spinner
from scc_firewall_manager_sdk.models.cdo_transaction import CdoTransaction

from sccfm_cli.commands.inventory.devices.cdfmc_managed_ftd.shared import (
    CdfmcFtdDeviceTargetCommand,
    ftd_check_option,
    ftd_device_filter_params,
)
from sccfm_cli.commands.inventory.options import (
    config_path_option,
    format_option,
    timeout_option,
    wait_option,
)
from sccfm_cli.utils import print_json
from sccfm_core.services.inventory.ftd_deploy_service import FtdDeployService


class FtdDeployCommand(CdfmcFtdDeviceTargetCommand):
    @property
    def name(self) -> str:
        return "deploy"

    @property
    def help_text(self) -> str:
        return "Deploy pending configuration changes to one or more " "cdFMC-managed FTD devices."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *ftd_device_filter_params(
                include_device_name=True,
                query_help_text="Filter devices by a Lucene query.",
                device_uids_help_text="List of device UIDs to deploy.",
            ),
            click.Option(
                ["--deployment-notes"],
                required=False,
                default=None,
                help="Notes for the deployment.",
            ),
            click.Option(
                ["--description"],
                required=False,
                default=None,
                help="Human-readable description for the deployment.",
            ),
            click.Option(
                ["--ignore-warnings"],
                is_flag=True,
                default=False,
                help="Ignore warnings from pre-validation and proceed with the deployment.",
            ),
            ftd_check_option(),
            wait_option(),
            timeout_option(),
            format_option(),
            config_path_option(),
        ]

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        check = cast(bool, kwargs.get("check", False))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        spinner_text = "Deploying FTD changes..."
        silent = (ctx.obj or {}).get("silent", False)

        live: Live | None = None
        if not silent:
            live = Live(
                Spinner("dots", text=spinner_text),
                console=self.console,
                refresh_per_second=10,
                transient=True,
            )
            live.start()

        try:
            targets = self.resolve_ftd_targets_from_kwargs(
                ctx=ctx,
                kwargs=kwargs,
                config=config,
                include_device_name=True,
            )

            if check:
                if live:
                    live.stop()
                    live = None
                self.report_check_targets(
                    targets,
                    output_format=output_format,
                    operation="deploy",
                )
                return

            devices = self.filter_online_devices(targets.devices)
            device_uids = [d.uid for d in devices]

            deployment_notes = cast(str | None, kwargs.get("deployment_notes"))
            description = cast(str | None, kwargs.get("description"))
            ignore_warnings = cast(bool, kwargs.get("ignore_warnings", False))

            deploy_service = FtdDeployService(config=config)
            transaction = self._trigger_deploy(
                deploy_service=deploy_service,
                device_uids=device_uids,
                deployment_notes=deployment_notes,
                description=description,
                ignore_warnings=ignore_warnings,
            )
        finally:
            if live:
                live.stop()

        transaction = self.wait_for_transaction(
            config=config,
            transaction=transaction,
            spinner_text=spinner_text if output_format != "json" else None,
            **kwargs,
        )

        self._render_transaction(
            transaction=transaction,
            device_count=len(device_uids),
            output_format=output_format,
            waited=cast(bool, kwargs.get("wait", False)),
        )

    @staticmethod
    def _trigger_deploy(
        *,
        deploy_service: FtdDeployService,
        device_uids: list[str],
        deployment_notes: str | None,
        description: str | None,
        ignore_warnings: bool,
    ) -> CdoTransaction:
        if len(device_uids) == 1:
            return deploy_service.deploy_single(
                device_uid=device_uids[0],
                deployment_notes=deployment_notes,
                description=description,
                ignore_warnings=ignore_warnings,
            )
        return deploy_service.deploy_multiple(
            device_uids=device_uids,
            deployment_notes=deployment_notes,
            description=description,
            ignore_warnings=ignore_warnings,
        )

    def _render_transaction(
        self,
        *,
        transaction: CdoTransaction,
        device_count: int,
        output_format: str,
        waited: bool,
    ) -> None:
        failed = self.is_failed_transaction(transaction)

        if output_format == "json":
            self._render_json(transaction=transaction)
        else:
            self._render_table(
                transaction=transaction,
                device_count=device_count,
                failed=failed,
                waited=waited,
            )

        if failed:
            ctx = click.get_current_context()
            ctx.exit(1)

    def _render_json(self, *, transaction: CdoTransaction) -> None:
        print_json(transaction.to_dict())

    def _render_table(
        self,
        *,
        transaction: CdoTransaction,
        device_count: int,
        failed: bool = False,
        waited: bool = False,
    ) -> None:
        if waited:
            icon = "[red]\u2717[/red]" if failed else "[green]\u2713[/green]"
            verb = "failed" if failed else "completed"
            self.console.print(f"{icon} Deploy {verb} for {device_count} device(s).")
            self.console.print(f"  [bold]Status:[/bold] {transaction.cdo_transaction_status}")
            if transaction.error_message:
                self.console.print(f"  [bold]Error:[/bold] {transaction.error_message}")
            return

        if failed:
            self.console.print(f"[red]\u2717[/red] Deploy failed for {device_count} device(s).")
        else:
            self.console.print(
                f"[green]\u2713[/green] Deploy triggered for {device_count} device(s)."
            )
        self.console.print(f"  [bold]Transaction UID:[/bold] {transaction.transaction_uid}")
        self.console.print(f"  [bold]Status:[/bold] {transaction.cdo_transaction_status}")
        if transaction.error_message:
            self.console.print(f"  [bold]Error:[/bold] {transaction.error_message}")
        if transaction.transaction_polling_url:
            self.console.print(f"  [bold]Polling URL:[/bold] {transaction.transaction_polling_url}")
