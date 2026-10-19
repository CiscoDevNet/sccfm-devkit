# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from typing import Any, Sequence, cast

import click
from rich.console import Console
from scc_firewall_manager_sdk import (
    AsaCreateOrUpdateInput,
    ConnectorType,
    Device,
    Labels,
)

from cisco_sccfm_cli.commands.base import BaseCommand
from cisco_sccfm_cli.commands.inventory.options import config_path_option, format_option
from cisco_sccfm_cli.option_metadata import sensitive_option
from cisco_sccfm_cli.utils import print_json, with_spinner
from cisco_sccfm_core import ASA_ENTITY_TYPES, InventoryService, build_device_type_filter
from cisco_sccfm_core.services.inventory import AsaOnboardService


class AsaOnboardCommand(BaseCommand):
    def __init__(self, console: Console) -> None:
        super().__init__(console)

    @property
    def name(self) -> str:
        return "onboard"

    @property
    def help_text(self) -> str:
        return "Onboard an ASA device to SCC Firewall Manager."

    def build_params(self) -> Sequence[click.Parameter]:
        return [
            click.Option(
                ["--name"],
                required=True,
                help="Human-readable name for the ASA device.",
            ),
            click.Option(
                ["--device-address"],
                required=False,
                default=None,
                callback=self._validate_device_address,
                help="Device address in the form host:port.",
            ),
            click.Option(
                ["--username"],
                required=False,
                default=None,
                help="Username used to authenticate with the device.",
            ),
            sensitive_option(
                click.Option(
                    ["--password"],
                    required=False,
                    default=None,
                    hide_input=True,
                    help="Password used to authenticate with the device.",
                ),
            ),
            click.Option(
                ["--connector-type"],
                required=False,
                default=None,
                type=click.Choice([ct.value for ct in ConnectorType], case_sensitive=True),
                help="Connector type used to communicate with the device.",
            ),
            click.Option(
                ["--connector-name"],
                required=False,
                callback=self._validate_connector_name,
                help=(
                    "Name of the Secure Device Connector (SDC) to use "
                    "(required when connector-type is SDC)."
                ),
            ),
            click.Option(
                ["--ignore-certificate"],
                is_flag=True,
                default=False,
                show_default=True,
                help="Skip certificate validation when onboarding.",
            ),
            click.Option(
                ["--grouped-labels"],
                type=str,
                help=(
                    "Grouped labels in JSON format, " 'e.g., \'{"environment": ["prod", "us-west"]}'
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

    @with_spinner("Onboarding ASA device...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        check = cast(bool, kwargs.get("check", False))
        name = cast(str, kwargs.get("name"))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        inventory_service = InventoryService(config=config)

        if check:
            self._handle_check(inventory_service, name, output_format)
            return

        for required_field in ("device_address", "username", "connector_type"):
            if not kwargs.get(required_field):
                ctx.fail(
                    f"--{required_field.replace('_', '-')} is required when not using --check."
                )

        password = cast(str | None, kwargs.get("password"))
        if not password:
            password = self._prompt_sensitive("Password")
            kwargs = {**kwargs, "password": password}

        asa_input = self._build_asa_input(ctx, **kwargs)

        device_page = inventory_service.get_devices(
            limit=1,
            offset=0,
            query=self._asa_name_query(asa_input.name),
        )
        if device_page.count is not None and device_page.count > 0:
            ctx.fail(f"ASA device with name {asa_input.name} already exists.")
        asa_onboard_service = AsaOnboardService(config=config)
        device: Device = asa_onboard_service.onboard_asa(asa_create_or_update_input=asa_input)

        if output_format == "json":
            print_json(device.to_dict())
        else:
            self.console.print(f"[green]\u2713[/green] Successfully onboarded ASA: {device.name}")
            self.console.print(f"  UID: {device.uid}")

    def _handle_check(
        self,
        inventory_service: InventoryService,
        name: str,
        output_format: str,
    ) -> None:
        """Check if a device with the given name exists."""
        device_page = inventory_service.get_devices(
            limit=1,
            offset=0,
            query=self._asa_name_query(name),
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
                    "entity_type": "ASA device",
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
                f"[green]\u2713[/green] ASA device '{name}' not found; onboard can proceed."
            )
        else:
            self.console.print(
                f"[yellow]![/yellow] ASA device '{name}' already exists; onboard would fail."
            )

    def _build_asa_input(self, ctx: click.Context, **kwargs: Any) -> AsaCreateOrUpdateInput:
        """Build AsaCreateOrUpdateInput from command parameters."""
        name = cast(str, kwargs.get("name"))
        device_address = cast(str, kwargs.get("device_address"))
        username = cast(str, kwargs.get("username"))
        password = cast(str, kwargs.get("password"))
        connector_type_str = cast(str, kwargs.get("connector_type"))
        connector_name = cast(str | None, kwargs.get("connector_name"))
        ignore_certificate = cast(bool, kwargs.get("ignore_certificate", False))
        grouped_labels_str = cast(str | None, kwargs.get("grouped_labels"))
        ungrouped_labels = cast(tuple[str, ...] | None, kwargs.get("ungrouped_labels"))

        connector_type = ConnectorType(connector_type_str)

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

        return AsaCreateOrUpdateInput(
            name=name,
            deviceAddress=device_address,
            username=username,
            password=password,
            connectorType=connector_type,
            connectorName=connector_name,
            ignoreCertificate=ignore_certificate,
            labels=labels,
        )

    @staticmethod
    def _asa_name_query(name: str) -> str:
        """Build the inventory query for a named ASA device."""
        return f"{build_device_type_filter(ASA_ENTITY_TYPES)} AND name:{name}"

    @staticmethod
    def _validate_device_address(
        ctx: click.Context, param: click.Parameter, value: str | None
    ) -> str | None:
        """Validate device address is in the format host:port."""
        if not value:
            return value

        if ":" not in value:
            raise click.BadParameter("Device address must be in the format host:port")

        parts = value.rsplit(":", 1)
        if len(parts) != 2:
            raise click.BadParameter("Device address must be in the format host:port")

        host, port_str = parts
        if not host:
            raise click.BadParameter("Host cannot be empty")

        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                raise click.BadParameter("Port must be between 1 and 65535")
        except ValueError:
            raise click.BadParameter("Port must be a valid integer")

        return value

    @staticmethod
    def _validate_connector_name(
        ctx: click.Context, param: click.Parameter, value: str | None
    ) -> str | None:
        """Validate connector_name is provided when connector_type is SDC."""
        connector_type = ctx.params.get("connector_type")
        if connector_type == ConnectorType.SDC.value and not value:
            raise click.BadParameter("--connector-name is required when --connector-type is SDC")
        return value
