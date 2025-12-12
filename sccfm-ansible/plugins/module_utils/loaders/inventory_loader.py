from __future__ import annotations

from typing import List, Optional

from ansible.errors import AnsibleParserError
from scc_firewall_manager_sdk import ApiException, Device, DevicePage

from sccfm_core.services import InventoryService
from sccfm_core.types import ConfigLike


class InventoryLoader:
    def __init__(self, *, config: ConfigLike, limit: int, query: Optional[str]) -> None:
        self._config = config
        self._limit = limit
        self._query = query
        self._inventory_service = InventoryService(config)

    def load_devices(self) -> List[Device]:
        try:
            return self._fetch_all_pages()
        except ApiException as exc:
            raise AnsibleParserError(f"Failed to load SCCFM devices: {exc.body or exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise AnsibleParserError(f"Failed to load SCCFM devices: {exc}") from exc

    def _fetch_all_pages(self) -> List[Device]:
        devices: List[Device] = []
        offset = 0

        while True:
            page: DevicePage = self._inventory_service.get_devices(
                limit=self._limit,
                offset=offset,
                query=self._query,
            )
            page_items = list(page.items or [])
            devices.extend(page_items)

            offset += len(page_items)
            total_count = page.count or 0
            if not page_items or offset >= total_count:
                break

        return devices
