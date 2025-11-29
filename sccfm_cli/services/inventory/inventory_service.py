from __future__ import annotations

from scc_firewall_manager_sdk import DevicePage, InventoryApi

from sccfm_cli.factories import ApiClientFactory
from sccfm_cli.models import Config


class InventoryService:
    def __init__(self, config: Config) -> None:
        api_client = ApiClientFactory().build(config)
        self.inventory_api = InventoryApi(api_client)

    def get_devices(
        self, *, config: Config, limit: int, offset: int, query: str | None
    ) -> DevicePage:
        return self.inventory_api.get_devices(limit=str(limit), offset=str(offset), q=query)

    def get_managers(
        self, *, config: Config, limit: int, offset: int, query: str = ""
    ) -> DevicePage:
        return self.inventory_api.get_device_managers(limit=str(limit), offset=str(offset), q=query)
