import json
from typing import Any, Sequence, cast

import click
from rich.console import Console
from scc_firewall_manager_sdk import (
    Device,
    EntityType,
    ZtpOnboardingInput,
)

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.options import config_path_option, format_option
from sccfm_cli.utils import with_spinner
from sccfm_core import FTD_LICENSES, InventoryService
from sccfm_core.services.inventory import FtdZtpOnboardService


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
            click.Option(
                ["--admin-password"],
                default=None,
                help=(
                    "Initial provisioning password for the device. "
                    "Required for setup if a password has not already been set on the device."
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
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        inventory_service = InventoryService(config=config)

        if check:
            self._handle_check(inventory_service, name, output_format)
            return

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

        ztp_input = self._build_ztp_input(**kwargs)

        ztp_onboard_service = FtdZtpOnboardService(config=config)
        device: Device = ztp_onboard_service.onboard_ftd_ztp(ztp_onboarding_input=ztp_input)

        uid = device.uid

        if output_format == "json":
            self.console.print(json.dumps({"uid": uid}, indent=2))
        else:
            if uid:
                self.console.print(uid)
            else:
                self.console.print("[yellow]Device UID not available[/yellow]")

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
            self.console.print(
                json.dumps(
                    {
                        "entity_type": "cdFMC-managed FTD device",
                        "identifier": name,
                        "operation": "onboard-ztp",
                        "exists": exists,
                        "can_proceed": can_proceed,
                        "reason": reason,
                        "device": device_data,
                    },
                    indent=2,
                    default=str,
                )
            )
            return

        if can_proceed:
            self.console.print(
                f"[green]\u2713[/green] FTD device '{name}' not found; onboard-ztp can proceed."
            )
        else:
            self.console.print(
                f"[yellow]![/yellow] FTD device '{name}' already exists; onboard-ztp would fail."
            )

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
        return f"deviceType:{EntityType.CDFMC_MANAGED_FTD.value} AND name:{name}"
