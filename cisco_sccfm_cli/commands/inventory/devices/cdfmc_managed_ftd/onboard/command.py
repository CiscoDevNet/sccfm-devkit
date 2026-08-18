# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from rich.console import Console
from scc_firewall_manager_sdk import (
    Device,
    EntityType,
    FtdCreateOrUpdateInput,
    Labels,
)

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.inventory.options import config_path_option, format_option
from cisco_sccfm_cli.utils import print_json, with_spinner
from cisco_sccfm_core import FTD_LICENSES, FTDV_PERFORMANCE_TIERS, InventoryService
from cisco_sccfm_core.services.inventory import FtdOnboardService


class FtdOnboardCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)

    @property
    def name(self) -> str:
        return "onboard"

    @property
    def help_text(self) -> str:
        return "Onboard a cdFMC-managed FTD device (non-ZTP)."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            click.Option(
                ["--name", "-n"],
                required=True,
                help="Human-readable name for the FTD device.",
            ),
            click.Option(
                ["--fmc-access-policy-uid"],
                required=True,
                help="UUID of the FMC access policy to apply to this device.",
            ),
            click.Option(
                ["--licenses"],
                required=True,
                multiple=True,
                type=click.Choice(FTD_LICENSES, case_sensitive=True),
                help=(
                    "License(s) to apply to the device. "
                    "Can be specified multiple times (e.g. --licenses BASE --licenses CARRIER)."
                ),
            ),
            click.Option(
                ["--virtual"],
                is_flag=True,
                default=False,
                help="Indicate that the FTD is a virtual device. Requires --performance-tier.",
            ),
            click.Option(
                ["--performance-tier"],
                default=None,
                type=click.Choice(FTDV_PERFORMANCE_TIERS, case_sensitive=True),
                help=(
                    "Performance tier of the FTDv (required when --virtual is set, "
                    "e.g., FTDv5, FTDv10, FTDv20)."
                ),
            ),
            click.Option(
                ["--grouped-labels"],
                type=str,
                default=None,
                help=(
                    "Grouped labels in JSON format, e.g., "
                    '\'{"environment": ["prod", "us-west"]}\'.'
                ),
            ),
            click.Option(
                ["--ungrouped-labels"],
                multiple=True,
                help="Free-form labels to assign to the device (can be specified multiple times).",
            ),
            click.Option(
                ["--check"],
                is_flag=True,
                default=False,
                help="Run a preflight check without onboarding.",
            ),
            config_path_option(),
            format_option(),
        ]

    @with_spinner("Onboarding cdFMC-managed FTD device...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        check = cast(bool, kwargs.get("check", False))
        name = cast(str, kwargs.get("name"))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        inventory_service = InventoryService(config=config)

        if check:
            self._handle_check(inventory_service, name, output_format)
            return

        virtual = cast(bool, kwargs.get("virtual", False))
        performance_tier = cast(str | None, kwargs.get("performance_tier"))

        if virtual and not performance_tier:
            ctx.fail("--performance-tier is required when --virtual is set.")

        licenses = cast(tuple[str, ...], kwargs.get("licenses", ()))
        if not licenses:
            ctx.fail("--licenses is required.")

        device_page = inventory_service.get_devices(
            limit=1,
            offset=0,
            query=self._ftd_name_query(name),
        )
        if device_page.count is not None and device_page.count > 0:
            ctx.fail(f"cdFMC-managed FTD device with name '{name}' already exists.")

        ftd_input = self._build_ftd_input(ctx, **kwargs)

        ftd_onboard_service = FtdOnboardService(config=config)
        device: Device = ftd_onboard_service.onboard_ftd(ftd_create_or_update_input=ftd_input)

        cli_key = device.cd_fmc_info.cli_key if device.cd_fmc_info else None

        if output_format == "json":
            print_json({"cli_key": cli_key})
        else:
            if cli_key:
                self.console.print(cli_key)
            else:
                self.console.print("[yellow]CLI key not available[/yellow]")

    def _handle_check(
        self,
        inventory_service: InventoryService,
        name: str,
        output_format: str,
    ) -> None:
        device_page = inventory_service.get_devices(
            limit=1,
            offset=0,
            query=self._ftd_name_query(name),
        )
        exists = device_page.count is not None and device_page.count > 0
        can_proceed = not exists
        reason = "not_found" if can_proceed else "already_exists"

        if output_format == "json":
            device_data = None
            if exists and device_page.items:
                device_data = device_page.items[0].to_dict()
            print_json(
                {
                    "entity_type": "cdFMC-managed FTD device",
                    "identifier": name,
                    "operation": "onboard",
                    "exists": exists,
                    "can_proceed": can_proceed,
                    "reason": reason,
                    "device": device_data,
                }
            )
            return

        if can_proceed:
            self.console.print(
                f"[green]\u2713[/green] FTD device '{name}' not found; onboard can proceed."
            )
        else:
            self.console.print(
                f"[yellow]![/yellow] FTD device '{name}' already exists; onboard would fail."
            )

    def _build_ftd_input(self, ctx: click.Context, **kwargs: Any) -> FtdCreateOrUpdateInput:
        name = cast(str, kwargs.get("name"))
        fmc_access_policy_uid = cast(str, kwargs.get("fmc_access_policy_uid"))
        licenses = list(cast(tuple[str, ...], kwargs.get("licenses", ())))
        virtual = cast(bool | None, kwargs.get("virtual"))
        performance_tier = cast(str | None, kwargs.get("performance_tier"))
        grouped_labels_str = cast(str | None, kwargs.get("grouped_labels"))
        ungrouped_labels = cast(tuple[str, ...] | None, kwargs.get("ungrouped_labels"))

        grouped_labels_dict = None
        if grouped_labels_str:
            try:
                grouped_labels_dict = json.loads(grouped_labels_str)
            except json.JSONDecodeError as e:
                ctx.fail(f"Invalid JSON for --grouped-labels: {e}")

        labels = None
        if grouped_labels_dict or ungrouped_labels:
            labels = Labels(
                groupedLabels=grouped_labels_dict,
                ungroupedLabels=list(ungrouped_labels) if ungrouped_labels else None,
            )

        return FtdCreateOrUpdateInput(
            deviceType="CDFMC_MANAGED_FTD",
            fmcAccessPolicyUid=fmc_access_policy_uid,
            name=name,
            licenses=licenses,
            virtual=virtual if virtual else None,
            performanceTier=performance_tier,
            labels=labels,
        )

    @staticmethod
    def _ftd_name_query(name: str) -> str:
        escaped = name.replace("\\", "\\\\").replace('"', '\\"')
        return f'deviceType:{EntityType.CDFMC_MANAGED_FTD.value} AND name:"{escaped}"'
