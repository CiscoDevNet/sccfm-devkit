# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from scc_firewall_manager_sdk import Device, DevicePage, InventoryApi

from cisco_sccfm_core.factories import ApiClientFactory
from cisco_sccfm_core.types import ConfigLike


class InventoryService:
    def __init__(self, config: ConfigLike) -> None:
        api_client = ApiClientFactory().build(config)
        self.inventory_api = InventoryApi(api_client)

    def get_devices(self, *, limit: int, offset: int, query: str | None) -> DevicePage:
        return self.inventory_api.get_devices(limit=str(limit), offset=str(offset), q=query)

    def get_device_by_uid(self, device_uid: str) -> Device:
        return self.inventory_api.get_device(device_uid=device_uid)

    def get_managers(self, *, limit: int, offset: int, query: str | None = None) -> DevicePage:
        return self.inventory_api.get_device_managers(limit=str(limit), offset=str(offset), q=query)
