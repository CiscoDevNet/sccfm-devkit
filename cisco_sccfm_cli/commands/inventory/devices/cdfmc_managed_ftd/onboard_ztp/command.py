# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence, cast

import click
from rich.console import Console
from scc_firewall_manager_sdk import (
    Device,
    DevicePage,
    EntityType,
    ZtpOnboardingInput,
)

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.inventory.options import config_path_option, format_option
from cisco_sccfm_cli.option_metadata import sensitive_option
from cisco_sccfm_cli.utils import print_json, with_spinner
from cisco_sccfm_core import FTD_LICENSES, InventoryService
from cisco_sccfm_core.services.inventory import FtdZtpOnboardService


@dataclass(frozen=True)
class _ConflictResult:
    reason: str  # "already_exists" | "name_conflict"
    device: Device


class FtdZtpOnboardCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)

    @property
    def name(self) -> str:
        return "onboard-ztp"

    @property
    def help_text(self) -> str:
        return "Onboard a cdFMC-managed FTD device using Zero-Touch Provisioning (ZTP)."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            click.Option(
                ["--name", "-n"],
                required=True,
                help="Human-readable name for the FTD device.",
            ),
            click.Option(
                ["--serial-number", "-s"],
                required=True,
                help=(
                    "Serial number of the FTD device. When plugged in and connected to the "
                    "Internet, the device will automatically register to this tenant."
                ),
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
                ["--fmc-access-policy-uid"],
                required=True,
                help="UUID of the FMC access policy to apply to this device.",
            ),
            sensitive_option(
                click.Option(
                    ["--admin-password"],
                    default=None,
                    envvar="SCCFM_FTD_ADMIN_PASSWORD",
                    show_envvar=True,
                    help=(
                        "Initial provisioning password for the device. Required for setup if a "
                        "password has not already been set on the device. For secure "
                        "non-interactive use, set SCCFM_FTD_ADMIN_PASSWORD."
                    ),
                ),
            ),
            click.Option(
                ["--device-group-uid"],
                default=None,
                help="UUID of the device group to assign this device to after registration.",
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

    @with_spinner("Onboarding cdFMC-managed FTD device via ZTP...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        check = cast(bool, kwargs.get("check", False))
        name = cast(str, kwargs.get("name"))
        serial_number = cast(str, kwargs.get("serial_number"))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        inventory_service = InventoryService(config=config)

        if check:
            self._handle_check(inventory_service, name, serial_number, output_format)
            return

        licenses = cast(tuple[str, ...], kwargs.get("licenses", ()))
        if not licenses:
            ctx.fail("--licenses is required.")

        conflict = self._find_conflict(inventory_service, name, serial_number)
        if conflict is not None:
            if conflict.reason == "already_exists":
                ctx.fail(
                    f"cdFMC-managed FTD device '{name}' with serial '{serial_number}' "
                    f"is already onboarded (uid: {conflict.device.uid})."
                )
            else:  # name_conflict
                ctx.fail(
                    f"A cdFMC-managed FTD device named '{name}' already exists "
                    f"with a different serial number (uid: {conflict.device.uid})."
                )

        ztp_input = self._build_ztp_input(**kwargs)
        ztp_onboard_service = FtdZtpOnboardService(config=config)
        device: Device = ztp_onboard_service.onboard_ftd_ztp(ztp_onboarding_input=ztp_input)

        uid = device.uid
        if output_format == "json":
            print_json({"uid": uid})
        else:
            if uid:
                self.console.print(uid)
            else:
                self.console.print("[yellow]Device UID not available[/yellow]")

    def _handle_check(
        self,
        inventory_service: InventoryService,
        name: str,
        serial_number: str,
        output_format: str,
    ) -> None:
        conflict = self._find_conflict(inventory_service, name, serial_number)
        can_proceed = conflict is None
        reason = conflict.reason if conflict is not None else "not_found"

        if output_format == "json":
            device_data = conflict.device.to_dict() if conflict is not None else None
            print_json(
                {
                    "entity_type": "cdFMC-managed FTD device",
                    "identifier": {"name": name, "serial_number": serial_number},
                    "operation": "onboard-ztp",
                    "exists": conflict is not None,
                    "can_proceed": can_proceed,
                    "reason": reason,
                    "device": device_data,
                }
            )
            return

        if can_proceed:
            self.console.print(
                f"[green]\u2713[/green] No conflicts found for '{name}'; onboard-ztp can proceed."
            )
        elif reason == "already_exists":
            self.console.print(
                f"[yellow]![/yellow] FTD device '{name}' with serial '{serial_number}' "
                f"is already onboarded; onboard-ztp would be a no-op."
            )
        else:  # name_conflict
            self.console.print(
                f"[red]✗[/red] A device named '{name}' already exists with a different serial; "
                f"onboard-ztp would fail."
            )

    def _find_conflict(
        self,
        inventory_service: InventoryService,
        name: str,
        serial_number: str,
    ) -> _ConflictResult | None:
        name_page: DevicePage = inventory_service.get_devices(
            limit=1, offset=0, query=self._ftd_name_query(name)
        )
        name_match = name_page.items[0] if name_page.count and name_page.items else None

        if name_match is None:
            return None

        if name_match.serial == serial_number:
            return _ConflictResult(reason="already_exists", device=name_match)

        return _ConflictResult(reason="name_conflict", device=name_match)

    def _build_ztp_input(self, **kwargs: Any) -> ZtpOnboardingInput:
        name = cast(str, kwargs.get("name"))
        serial_number = cast(str, kwargs.get("serial_number"))
        fmc_access_policy_uid = cast(str, kwargs.get("fmc_access_policy_uid"))
        licenses = list(cast(tuple[str, ...], kwargs.get("licenses", ())))
        admin_password = cast(str | None, kwargs.get("admin_password"))
        device_group_uid = cast(str | None, kwargs.get("device_group_uid"))

        return ZtpOnboardingInput(
            name=name,
            serialNumber=serial_number,
            fmcAccessPolicyUid=fmc_access_policy_uid,
            licenses=licenses,
            adminPassword=admin_password,
            deviceGroupUid=device_group_uid,
        )

    @staticmethod
    def _ftd_name_query(name: str) -> str:
        escaped = name.replace("\\", "\\\\").replace('"', '\\"')
        return f'deviceType:{EntityType.CDFMC_MANAGED_FTD.value} AND name:"{escaped}"'
