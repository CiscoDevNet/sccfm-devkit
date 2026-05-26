# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click
from rich.live import Live
from rich.spinner import Spinner
from scc_firewall_manager_sdk.models.cdo_transaction import CdoTransaction

from sccfm_cli.commands.inventory.devices.asa.shared import (
    AsaDeviceTargetCommand,
    AsaDeviceTargets,
    asa_check_option,
    asa_device_filter_params,
)
from sccfm_cli.commands.inventory.options import (
    config_path_option,
    format_option,
    timeout_option,
    wait_option,
)
from sccfm_cli.utils import print_json
from sccfm_core.services.inventory import (
    AsaUpgradeService,
    AsaUpgradeVersionService,
    get_asdm_compatibility_info,
    is_version_downgrade,
)


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
            wait_option(),
            timeout_option(),
            format_option(),
            config_path_option(),
        ]

    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        check = cast(bool, kwargs.get("check", False))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        spinner_text = "Triggering ASA upgrade..."
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
            targets = self.resolve_asa_targets_from_kwargs(
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

            self._validate_version_specified(ctx=ctx, kwargs=kwargs)

            software_version = cast(str | None, kwargs.get("software_version"))
            asdm_version = cast(str | None, kwargs.get("asdm_version"))
            stage_upgrade = cast(bool, kwargs.get("stage_upgrade", False))
            force_upgrade = cast(bool, kwargs.get("force_upgrade", False))
            ignore_maintenance_window = cast(bool, kwargs.get("ignore_maintenance_window", False))
            upgrade_name = cast(str | None, kwargs.get("upgrade_name"))

            if software_version:
                self._validate_no_downgrade(
                    ctx=ctx,
                    targets=targets,
                    target_version=software_version,
                    current_version_attr="software_version",
                    label="Software",
                )
                self._validate_asdm_compatibility(
                    ctx=ctx,
                    config=config,
                    targets=targets,
                    software_version=software_version,
                    asdm_version=asdm_version,
                )

            if asdm_version:
                if not software_version:
                    self._validate_asdm_compatibility_with_current_software(
                        ctx=ctx,
                        config=config,
                        targets=targets,
                        asdm_version=asdm_version,
                    )

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

    def _validate_asdm_compatibility(
        self,
        *,
        ctx: click.Context,
        config: Any,
        targets: AsaDeviceTargets,
        software_version: str,
        asdm_version: str | None,
    ) -> None:
        version_service = AsaUpgradeVersionService(config=config)
        compat = version_service.get_compatible_versions(device_uids=targets.device_uids)
        info = get_asdm_compatibility_info(compat.common_versions, software_version)

        if info is None:
            ctx.fail(
                f"Software version {software_version} is not compatible "
                f"with the selected device(s)."
            )
            return

        if asdm_version is not None:
            if asdm_version not in info.compatible_asdm_versions:
                ctx.fail(
                    f"ASDM version {asdm_version} is not compatible with "
                    f"software version {software_version}. "
                    f"Minimum required ASDM version is {info.minimum_asdm_version}."
                )
            return

        mismatched = [
            d for d in targets.devices if d.asdm_version not in info.compatible_asdm_versions
        ]
        if mismatched:
            ctx.fail(
                f"Software version {software_version} requires "
                f"ASDM >= {info.minimum_asdm_version}. "
                f"{len(mismatched)} device(s) currently run an incompatible ASDM version. "
                f"Add --asdm-version=<version> to include the ASDM upgrade. "
                f"Run 'compatible-versions' to see available ASDM options."
            )

    @staticmethod
    def _validate_no_downgrade(
        *,
        ctx: click.Context,
        targets: AsaDeviceTargets,
        target_version: str,
        current_version_attr: str,
        label: str,
    ) -> None:
        downgraded = [
            d
            for d in targets.devices
            if getattr(d, current_version_attr)
            and is_version_downgrade(target_version, getattr(d, current_version_attr))
        ]
        if downgraded:
            current = getattr(downgraded[0], current_version_attr)
            ctx.fail(
                f"{label} version {target_version} is lower than the current "
                f"device {label} version {current}. Downgrades are not supported."
            )

    def _validate_asdm_compatibility_with_current_software(
        self,
        *,
        ctx: click.Context,
        config: Any,
        targets: AsaDeviceTargets,
        asdm_version: str,
    ) -> None:
        """Validate ASDM version against each device's current software version."""
        version_service = AsaUpgradeVersionService(config=config)
        compat = version_service.get_compatible_versions(device_uids=targets.device_uids)

        for device in targets.devices:
            software = device.software_version
            if not software:
                continue
            info = get_asdm_compatibility_info(compat.common_versions, software)
            if info is None:
                continue
            if asdm_version not in info.compatible_asdm_versions:
                ctx.fail(
                    f"ASDM version {asdm_version} is not compatible with "
                    f"device software version {software}. "
                    f"Minimum required ASDM version is {info.minimum_asdm_version}."
                )
                return

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
        print_json(transaction.to_dict())

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
