from __future__ import annotations

from scc_firewall_manager_sdk import DevicePage, InventoryApi

from sccfm_core.factories import ApiClientFactory
from sccfm_core.types import ConfigLike


class InventoryService:
    def __init__(self, config: ConfigLike) -> None:
        api_client = ApiClientFactory().build(config)
        self.inventory_api = InventoryApi(api_client)

    def get_devices(self, *, limit: int, offset: int, query: str | None) -> DevicePage:
        return self.inventory_api.get_devices(limit=str(limit), offset=str(offset), q=query)

    def get_managers(
        self, *, config: ConfigLike, limit: int, offset: int, query: str = ""
    ) -> DevicePage:
        return self.inventory_api.get_device_managers(limit=str(limit), offset=str(offset), q=query)
