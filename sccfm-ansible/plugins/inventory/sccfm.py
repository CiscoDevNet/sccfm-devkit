# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from ansible.errors import AnsibleParserError
from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.utils.display import Display
from scc_firewall_manager_sdk import Device

from cisco_sccfm_core.services.profile_service import ProfileService

from ..module_utils.config import Config
from ..plugin_utils.inventory_host_builder import InventoryHostBuilder
from ..plugin_utils.inventory_loader import InventoryLoader

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
  profile:
    description: Named SCCFM profile configured by C(sccfm-cli configure).
    required: false
    type: str
    default: default
  config_path:
    description: Optional path to the canonical SCCFM profile configuration file.
    required: false
    type: path
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
profile: default
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
        profile = (
            self._template_string(cast(Optional[str], config_data.get("profile"))) or "default"
        )
        raw_config_path = self._template_string(cast(Optional[str], config_data.get("config_path")))
        stored = ProfileService(path=Path(raw_config_path) if raw_config_path else None).load(
            profile
        )
        if stored is None:
            raise AnsibleParserError(
                f"SCCFM profile '{profile}' not found. "
                f"Run 'sccfm-cli --profile {profile} configure' to set it up."
            )

        limit = int(cast(int | None, config_data.get("limit")) or 100)
        query = cast(Optional[str], config_data.get("query"))
        group = cast(Optional[str], config_data.get("group") or "sccfm")
        group_by_device_type = bool(config_data.get("group_by_device_type", False))

        try:
            config = Config(region=stored.region, api_token=stored.api_token)
        except ValueError as exc:
            raise AnsibleParserError(str(exc)) from exc

        region = config.region
        inventory_loader = InventoryLoader(config=config, limit=limit, query=query)
        devices: List[Device] = inventory_loader.load_devices()

        self._region = region

        if group:
            self.inventory.add_group(group)
            self.inventory.set_variable(group, "sccfm_region", region)
            self.inventory.set_variable(group, "sccfm_profile", profile)

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
