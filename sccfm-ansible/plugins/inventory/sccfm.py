from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, cast

from ansible.errors import AnsibleParserError
from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.utils.display import Display
from scc_firewall_manager_sdk import Device

from ..module_utils.builders import InventoryHostBuilder
from ..module_utils.config import Config
from ..module_utils.loaders import InventoryLoader

DOCUMENTATION = r"""
name: cisco.sccfm.sccfm
plugin_type: inventory
short_description: Load devices in SCC Firewall Manager as inventory hosts.
description:
  - Uses Cisco Security Cloud Control Firewall Manager (SCCFM) to enumerate
    devices using the REST APIs.
  - Each device becomes an inventory host with SCCFM metadata attached as host variables.
options:
  plugin:
    description: Ensure this plugin gets loaded.
    required: true
    choices: ["cisco.sccfm.sccfm"]
  region:
    description: SCCFM region to target (int, us, eu, apj, au, uae, in, or ci).
    env:
      - name: SCCFM_REGION
    required: true
    type: str
  api_token:
    description: API token for the SCCFM region.
    env:
      - name: SCCFM_API_TOKEN
    required: true
    type: str
    no_log: true
  limit:
    description: Page size to use when fetching devices.
    required: false
    type: int
    default: 100
  query:
    description: Optional text filter applied to device names.
    required: false
    type: str
  group:
    description: Group to place all discovered SCCFM devices into.
    required: false
    type: str
    default: sccfm
  group_by_device_type:
    description: Create groups based on device types (e.g., ASA, CDFMC_MANAGED_FTD).
    required: false
    type: bool
    default: false
"""

EXAMPLES = r"""
plugin: cisco.sccfm.sccfm
region: us
api_token: "{{ lookup('env', 'SCCFM_API_TOKEN') }}"
limit: 100
query: "asa"
group: sccfm
group_by_device_type: true
"""


class InventoryModule(BaseInventoryPlugin):
    NAME = "cisco.sccfm.sccfm"

    def __init__(self) -> None:
        super().__init__()
        self.display = Display()
        self._region: Optional[str] = None

    def verify_file(self, path: str) -> bool:
        valid = super().verify_file(path)
        if not valid:
            return False
        return path.endswith((".yml", ".yaml"))

    def parse(self, inventory: Any, loader: Any, path: str, cache: bool = True) -> None:
        super().parse(inventory, loader, path, cache=cache)

        config_data: Dict[str, Any] = self._read_config_data(path)
        region = self._template_string(cast(Optional[str], config_data.get("region")))
        api_token = self._template_string(cast(Optional[str], config_data.get("api_token")))

        if region is None:
            region = cast(Optional[str], os.getenv("SCCFM_REGION"))
        if api_token is None:
            api_token = cast(Optional[str], os.getenv("SCCFM_API_TOKEN"))

        if not region:
            raise AnsibleParserError(
                "SCCFM region is required. Set 'region' in the inventory file or "
                "export SCCFM_REGION."
            )
        if not api_token:
            raise AnsibleParserError(
                "SCCFM api_token is required. Set 'api_token' in the inventory file "
                "or export SCCFM_API_TOKEN."
            )

        limit = int(cast(int | None, config_data.get("limit")) or 100)
        query = cast(Optional[str], config_data.get("query"))
        group = cast(Optional[str], config_data.get("group") or "sccfm")
        group_by_device_type = bool(config_data.get("group_by_device_type", False))

        try:
            config = Config(region=region, api_token=api_token)
        except ValueError as exc:
            raise AnsibleParserError(str(exc)) from exc

        region = config.region
        inventory_loader = InventoryLoader(config=config, limit=limit, query=query)
        devices: List[Device] = inventory_loader.load_devices()

        self._region = region

        if group:
            self.inventory.add_group(group)
            self.inventory.set_variable(group, "sccfm_region", region)
            self.inventory.set_variable(group, "sccfm_api_token", api_token)

        host_builder = InventoryHostBuilder(inventory=self.inventory, region=region)

        for device in devices:
            host_builder.add_device_host(
                device=device,
                parent_group=group,
                group_by_device_type=group_by_device_type,
            )

    def _template_string(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            rendered = self.templar.template(value)
        except Exception as exc:  # noqa: BLE001 - surface template errors to users
            raise AnsibleParserError(f"Failed to render SCCFM config value: {exc}") from exc
        return cast(Optional[str], rendered)
