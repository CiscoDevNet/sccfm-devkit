from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from scc_firewall_manager_sdk import CdoTransaction

from sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    asa_check_option,
    asa_device_filter_params,
)
from sccfm_cli.commands.inventory.options import config_path_option, format_option
from sccfm_cli.utils import with_spinner
from sccfm_core.services.inventory import AsaUpgradeService


class AsaUpgradeTriggerCommand(AsaDeviceTargetCommand):
    @property
    def name(self) -> str:
        return "trigger"

    @property
    def help_text(self) -> str:
        return (
            "Trigger an ASA firmware/ASDM upgrade on one or more devices. "
            "Supports staging (download + readiness check only) or full upgrade."
        )

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *asa_device_filter_params(
                include_device_name=True,
                query_help_text="Filter devices by a Lucene query.",
                device_uids_help_text="List of device UIDs to upgrade.",
            ),
            click.Option(
                ["--software-version"],
                required=False,
                default=None,
                help="Target ASA firmware version (e.g. '9.18(4)').",
            ),
            click.Option(
                ["--asdm-version"],
                required=False,
                default=None,
                help="Target ASDM software version (e.g. '7.18(1.152)').",
            ),
            click.Option(
                ["--stage-upgrade"],
                is_flag=True,
                default=False,
                help=(
                    "Stage the upgrade only (download image + readiness checks). "
                    "The upgrade will NOT be applied to the device."
                ),
            ),
            click.Option(
                ["--force-upgrade"],
                is_flag=True,
                default=False,
                help="Force upgrade even if a staged upgrade already exists on the device.",
            ),
            click.Option(
                ["--ignore-maintenance-window"],
                is_flag=True,
                default=False,
                help="Allow upgrade even if the device is outside its maintenance window.",
            ),
            click.Option(
                ["--upgrade-name"],
                required=False,
                default=None,
                help="Human-readable name to identify and track the upgrade run.",
            ),
            asa_check_option(),
            format_option(),
            config_path_option(),
        ]

    @with_spinner("Triggering ASA upgrade...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        check = cast(bool, kwargs.get("check", False))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        targets = self.resolve_asa_targets_from_kwargs(
            ctx=ctx,
            kwargs=kwargs,
            config=config,
            include_device_name=True,
        )

        if check:
            self.report_check_targets(
                targets,
                output_format=output_format,
                operation="upgrade trigger",
            )
            return

        self._validate_version_specified(ctx=ctx, kwargs=kwargs)

        software_version = cast(str | None, kwargs.get("software_version"))
        asdm_version = cast(str | None, kwargs.get("asdm_version"))
        stage_upgrade = cast(bool, kwargs.get("stage_upgrade", False))
        force_upgrade = cast(bool, kwargs.get("force_upgrade", False))
        ignore_maintenance_window = cast(bool, kwargs.get("ignore_maintenance_window", False))
        upgrade_name = cast(str | None, kwargs.get("upgrade_name"))

        upgrade_service = AsaUpgradeService(config=config)
        transaction = self._trigger_upgrade(
            upgrade_service=upgrade_service,
            device_uids=targets.device_uids,
            software_version=software_version,
            asdm_version=asdm_version,
            stage_upgrade=stage_upgrade,
            force_upgrade=force_upgrade,
            ignore_maintenance_window=ignore_maintenance_window,
            upgrade_name=upgrade_name,
        )

        self._render_transaction(
            transaction=transaction,
            device_count=len(targets.device_uids),
            stage_upgrade=stage_upgrade,
            output_format=output_format,
        )

    @staticmethod
    def _validate_version_specified(ctx: click.Context, kwargs: Any) -> None:
        software_version = kwargs.get("software_version")
        asdm_version = kwargs.get("asdm_version")
        if not software_version and not asdm_version:
            ctx.fail("Provide at least one of --software-version or --asdm-version.")

    def _trigger_upgrade(
        self,
        *,
        upgrade_service: AsaUpgradeService,
        device_uids: list[str],
        software_version: str | None,
        asdm_version: str | None,
        stage_upgrade: bool,
        force_upgrade: bool,
        ignore_maintenance_window: bool,
        upgrade_name: str | None,
    ) -> CdoTransaction:
        is_single = len(device_uids) == 1
        if is_single:
            return upgrade_service.upgrade_single(
                device_uid=device_uids[0],
                software_version=software_version,
                asdm_version=asdm_version,
                stage_upgrade=stage_upgrade,
                force_upgrade=force_upgrade,
                ignore_maintenance_window=ignore_maintenance_window,
                name=upgrade_name,
            )
        return upgrade_service.upgrade_multiple(
            device_uids=device_uids,
            software_version=software_version,
            asdm_version=asdm_version,
            stage_upgrade=stage_upgrade,
            force_upgrade=force_upgrade,
            ignore_maintenance_window=ignore_maintenance_window,
            name=upgrade_name,
        )

    def _render_transaction(
        self,
        *,
        transaction: CdoTransaction,
        device_count: int,
        stage_upgrade: bool,
        output_format: str,
    ) -> None:
        if output_format == "json":
            self._render_json(transaction=transaction)
        else:
            self._render_table(
                transaction=transaction,
                device_count=device_count,
                stage_upgrade=stage_upgrade,
            )

    def _render_json(self, *, transaction: CdoTransaction) -> None:
        print(json.dumps(transaction.to_dict(), indent=2, ensure_ascii=False, default=str))

    def _render_table(
        self,
        *,
        transaction: CdoTransaction,
        device_count: int,
        stage_upgrade: bool,
    ) -> None:
        action = "Staging" if stage_upgrade else "Upgrade"
        self.console.print(
            f"[green]\u2713[/green] {action} triggered for {device_count} device(s)."
        )
        self.console.print(f"  [bold]Transaction UID:[/bold] {transaction.transaction_uid}")
        self.console.print(f"  [bold]Status:[/bold] {transaction.cdo_transaction_status}")
        if transaction.transaction_polling_url:
            self.console.print(f"  [bold]Polling URL:[/bold] {transaction.transaction_polling_url}")
