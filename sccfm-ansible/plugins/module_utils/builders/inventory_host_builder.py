from __future__ import annotations

from ansible.inventory.data import InventoryData
from scc_firewall_manager_sdk import Device


class InventoryHostBuilder:
    """Handles the addition of SCCFM devices to an Ansible inventory."""

    def __init__(self, inventory: InventoryData, region: str) -> None:
        self._inventory = inventory
        self._region = region

    def add_device_host(
        self,
        *,
        device: Device,
        parent_group: str | None,
        group_by_device_type: bool,
    ) -> None:
        """Add a device to the inventory as a host with appropriate grouping and variables."""
        target_group = self._determine_target_group(
            device=device,
            parent_group=parent_group,
            group_by_device_type=group_by_device_type,
        )

        self._inventory.add_host(device.name, target_group)
        self._set_host_variables(device=device)

    def _determine_target_group(
        self,
        *,
        device: Device,
        parent_group: str | None,
        group_by_device_type: bool,
    ) -> str | None:
        """Determine the target group for a device based on grouping settings."""
        if not group_by_device_type or not device.device_type:
            return parent_group

        # Sanitize group name: replace dots with underscores for valid Ansible group names
        device_type_group = str(device.device_type).replace("EntityType.", "")
        self._inventory.add_group(device_type_group)

        if parent_group:
            self._inventory.add_child(parent_group, device_type_group)

        return device_type_group

    def _set_host_variables(self, *, device: Device) -> None:
        """Set standard SCCFM variables for a host."""
        self._inventory.set_variable(device.name, "sccfm_uid", device.uid)
        self._inventory.set_variable(device.name, "sccfm_name", device.name)
        self._inventory.set_variable(device.name, "sccfm_region", self._region)
        self._inventory.set_variable(device.name, "sccfm_device_type", device.device_type)
        self._inventory.set_variable(
            device.name, "sccfm_connectivity_state", device.connectivity_state
        )
        self._inventory.set_variable(device.name, "sccfm_config_state", device.config_state)
        self._inventory.set_variable(device.name, "sccfm_software_version", device.software_version)
