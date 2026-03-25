from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from rich.live import Live
from rich.spinner import Spinner
from scc_firewall_manager_sdk.models.cdo_transaction import CdoTransaction

from sccfm_cli.commands.inventory.devices.ftd.shared import (
    FtdDeviceTargetCommand,
    FtdDeviceTargets,
    ftd_check_option,
    ftd_device_filter_params,
)
from sccfm_cli.commands.inventory.options import (
    config_path_option,
    format_option,
    timeout_option,
    wait_option,
)
from sccfm_core.services.inventory import (
    FtdUpgradeService,
    FtdUpgradeVersionService,
    resolve_upgrade_package_uid,
)
from sccfm_core.services.inventory.asa_upgrade_version_service import is_version_downgrade


class FtdUpgradeTriggerCommand(FtdDeviceTargetCommand):
    @property
    def name(self) -> str:
        return "trigger"

    @property
    def help_text(self) -> str:
        return (
            "Trigger an FTD firmware upgrade on one or more devices. "
            "Supports staging (download + readiness check only) or full upgrade."
        )

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            *ftd_device_filter_params(
                include_device_name=True,
                query_help_text="Filter devices by a Lucene query.",
                device_uids_help_text="List of device UIDs to upgrade.",
            ),
            click.Option(
                ["--software-version"],
                required=True,
                help="Target FTD software version (e.g. '7.4.1').",
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
            ftd_check_option(),
            wait_option(),
            timeout_option(default=3600),
            format_option(),
            config_path_option(),
        ]

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        check = cast(bool, kwargs.get("check", False))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        spinner_text = "Triggering FTD upgrade..."
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
                    operation="upgrade trigger",
                )
                return

            software_version = cast(str, kwargs.get("software_version"))
            stage_upgrade = cast(bool, kwargs.get("stage_upgrade", False))
            ignore_maintenance_window = cast(bool, kwargs.get("ignore_maintenance_window", False))
            upgrade_name = cast(str | None, kwargs.get("upgrade_name"))

            upgrade_package_uid, targets = self._resolve_upgrade_package(
                ctx=ctx,
                config=config,
                targets=targets,
                software_version=software_version,
            )

            self._validate_no_downgrade(
                ctx=ctx,
                targets=targets,
                target_version=software_version,
            )

            upgrade_service = FtdUpgradeService(config=config)
            transaction = self._trigger_upgrade(
                upgrade_service=upgrade_service,
                device_uids=targets.device_uids,
                upgrade_package_uid=upgrade_package_uid,
                stage_upgrade=stage_upgrade,
                ignore_maintenance_window=ignore_maintenance_window,
                upgrade_name=upgrade_name,
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
            device_count=len(targets.device_uids),
            stage_upgrade=stage_upgrade,
            output_format=output_format,
            waited=cast(bool, kwargs.get("wait", False)),
        )

    @staticmethod
    def _validate_no_downgrade(
        *,
        ctx: click.Context,
        targets: FtdDeviceTargets,
        target_version: str,
    ) -> None:
        downgraded = [
            d
            for d in targets.devices
            if d.software_version and is_version_downgrade(target_version, d.software_version)
        ]
        if downgraded:
            current = downgraded[0].software_version
            ctx.fail(
                f"Software version {target_version} is lower than the current "
                f"device software version {current}. Downgrades are not supported."
            )

    def _resolve_upgrade_package(
        self,
        *,
        ctx: click.Context,
        config: Any,
        targets: FtdDeviceTargets,
        software_version: str,
    ) -> tuple[str, FtdDeviceTargets]:
        """Resolve the upgrade_package_uid and narrow targets to eligible devices.

        Devices that the API rejects during version lookup are excluded and
        a warning is printed for each.
        """
        version_service = FtdUpgradeVersionService(config=config)
        compat = version_service.get_compatible_versions(device_uids=targets.device_uids)

        for uid, reason in compat.skipped.items():
            device = targets.uid_to_device.get(uid)
            label = device.name if device else uid
            self.console.print(f"[blue]ℹ[/blue] [yellow]Skipping '{label}': {reason}[/yellow]")

        if not compat.per_device:
            ctx.fail("No devices returned compatible versions.")

        eligible = [d for d in targets.devices if d.uid in compat.per_device]
        targets = FtdDeviceTargets(
            devices=eligible,
            uid_to_device={d.uid: d for d in eligible},
            device_uids=[d.uid for d in eligible],
        )

        package_uid = resolve_upgrade_package_uid(compat.common_versions, software_version)
        if package_uid is None:
            ctx.fail(
                f"Software version {software_version} is not compatible "
                f"with the selected device(s). "
                f"Run 'compatible-versions' to see available options."
            )
        return package_uid or "", targets

    def _trigger_upgrade(
        self,
        *,
        upgrade_service: FtdUpgradeService,
        device_uids: list[str],
        upgrade_package_uid: str,
        stage_upgrade: bool,
        ignore_maintenance_window: bool,
        upgrade_name: str | None,
    ) -> CdoTransaction:
        is_single = len(device_uids) == 1
        if is_single:
            return upgrade_service.upgrade_single(
                device_uid=device_uids[0],
                upgrade_package_uid=upgrade_package_uid,
                stage_upgrade=stage_upgrade,
                ignore_maintenance_window=ignore_maintenance_window,
                name=upgrade_name,
            )
        return upgrade_service.upgrade_multiple(
            device_uids=device_uids,
            upgrade_package_uid=upgrade_package_uid,
            stage_upgrade=stage_upgrade,
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
        waited: bool,
    ) -> None:
        failed = self.is_failed_transaction(transaction)

        if output_format == "json":
            self._render_json(transaction=transaction)
        else:
            self._render_table(
                transaction=transaction,
                device_count=device_count,
                stage_upgrade=stage_upgrade,
                failed=failed,
                waited=waited,
            )

        if failed:
            ctx = click.get_current_context()
            ctx.exit(1)

    def _render_json(self, *, transaction: CdoTransaction) -> None:
        print(json.dumps(transaction.to_dict(), indent=2, ensure_ascii=False, default=str))

    def _render_table(
        self,
        *,
        transaction: CdoTransaction,
        device_count: int,
        stage_upgrade: bool,
        failed: bool = False,
        waited: bool = False,
    ) -> None:
        action = "Staging" if stage_upgrade else "Upgrade"

        if waited:
            icon = "[red]\u2717[/red]" if failed else "[green]\u2713[/green]"
            verb = "failed" if failed else "triggered"
            self.console.print(f"  [bold]Status:[/bold] {transaction.cdo_transaction_status}")
            self.console.print(f"{icon} {action} {verb} for {device_count} device(s).")
            if transaction.error_message:
                self.console.print(f"  [bold]Error:[/bold] {transaction.error_message}")
            return

        if failed:
            self.console.print(f"[red]\u2717[/red] {action} failed for {device_count} device(s).")
        else:
            self.console.print(
                f"[green]\u2713[/green] {action} triggered for {device_count} device(s)."
            )
        self.console.print(f"  [bold]Transaction UID:[/bold] {transaction.transaction_uid}")
        self.console.print(f"  [bold]Status:[/bold] {transaction.cdo_transaction_status}")
        if transaction.error_message:
            self.console.print(f"  [bold]Error:[/bold] {transaction.error_message}")
        if transaction.transaction_polling_url:
            self.console.print(f"  [bold]Polling URL:[/bold] {transaction.transaction_polling_url}")
