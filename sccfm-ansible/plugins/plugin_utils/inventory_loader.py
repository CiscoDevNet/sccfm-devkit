# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Load SCCFM device records for the inventory plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ansible.errors import AnsibleParserError

if TYPE_CHECKING:
    from scc_firewall_manager_sdk import Device, DevicePage

    from cisco_sccfm_core.types import ConfigLike

try:
    from scc_firewall_manager_sdk import ApiException

    from cisco_sccfm_core import SccApiError
    from cisco_sccfm_core.services import InventoryService
except ImportError as exc:
    _DEPENDENCY_IMPORT_ERROR: ImportError | None = exc
else:
    _DEPENDENCY_IMPORT_ERROR = None


class InventoryLoader:
    """Fetch all SCCFM device pages for a dynamic inventory refresh."""

    def __init__(self, *, config: "ConfigLike", limit: int, query: str | None) -> None:
        if _DEPENDENCY_IMPORT_ERROR is not None:
            raise AnsibleParserError(
                "cisco-sccfm-devkit must be installed on the Ansible controller "
                "to use the cisco.sccfm inventory plugin"
            ) from _DEPENDENCY_IMPORT_ERROR

        self._config = config
        self._limit = limit
        self._query = query
        self._inventory_service = InventoryService(config)

    def load_devices(self) -> list["Device"]:
        """Return all matching devices, translating API failures for Ansible."""
        try:
            return self._fetch_all_pages()
        except ApiException as exc:
            error = SccApiError.from_exception(exc)
            raise AnsibleParserError(f"Failed to load SCCFM devices: {error}") from exc
        except Exception as exc:
            raise AnsibleParserError(f"Failed to load SCCFM devices: {exc}") from exc

    def _fetch_all_pages(self) -> list["Device"]:
        devices: list["Device"] = []
        offset = 0

        while True:
            page: "DevicePage" = self._inventory_service.get_devices(
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
