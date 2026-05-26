# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, Sequence, cast

import click
from scc_firewall_manager_sdk import DevicePage

from sccfm_cli.commands.base import BaseCommand
from sccfm_cli.commands.inventory.devices.rendering import render_device_page
from sccfm_cli.commands.inventory.options import inventory_list_params
from sccfm_cli.utils import with_spinner
from sccfm_core.services import InventoryService


class DevicesListCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "list"

    @property
    def help_text(self) -> str:
        return "List devices."

    def build_params(self) -> Sequence[click.Parameter]:
        return inventory_list_params()

    @with_spinner("Fetching devices from SCC Firewall Manager...")
    def handle(self, ctx: click.Context, **kwargs: Any) -> None:
        limit = cast(int, kwargs.get("limit"))
        offset = cast(int, kwargs.get("offset"))
        query = cast(str | None, kwargs.get("query"))
        output_format = cast(str, kwargs.get("format"))

        config = self.get_profile(ctx=ctx, **kwargs)
        inventory_service = InventoryService(config)
        page: DevicePage = inventory_service.get_devices(
            limit=limit,
            offset=offset,
            query=query,
        )

        render_device_page(self.console, page, output_format, limit=limit, offset=offset)
