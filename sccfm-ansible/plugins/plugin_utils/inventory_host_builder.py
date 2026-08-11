# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Build Ansible inventory hosts from SCCFM device records."""

from __future__ import annotations

from typing import Protocol

from ansible.inventory.data import InventoryData


class DeviceLike(Protocol):
    """Device fields consumed while constructing inventory."""

    uid: str
    name: str
    device_type: object
    connectivity_state: object
    config_state: object
    software_version: str | None


class InventoryHostBuilder:
    """Add SCCFM devices to an Ansible inventory."""

    def __init__(self, inventory: InventoryData, region: str) -> None:
        self._inventory = inventory
        self._region = region

    def add_device_host(
        self,
        *,
        device: DeviceLike,
        parent_group: str | None,
        group_by_device_type: bool,
    ) -> None:
        """Add a device as a host with grouping and SCCFM metadata variables."""
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
        device: DeviceLike,
        parent_group: str | None,
        group_by_device_type: bool,
    ) -> str | None:
        """Determine the target group for a device based on grouping settings."""
        if not group_by_device_type or not device.device_type:
            return parent_group

        device_type_group = str(device.device_type).replace("EntityType.", "")
        self._inventory.add_group(device_type_group)

        if parent_group:
            self._inventory.add_child(parent_group, device_type_group)

        return device_type_group

    def _set_host_variables(self, *, device: DeviceLike) -> None:
        """Set standard SCCFM variables for a host."""
        self._inventory.set_variable(device.name, "sccfm_uid", device.uid)
        self._inventory.set_variable(device.name, "sccfm_name", device.name)
        self._inventory.set_variable(device.name, "sccfm_region", self._region)
        self._inventory.set_variable(
            device.name, "sccfm_device_type", str(device.device_type).replace("EntityType.", "")
        )
        self._inventory.set_variable(
            device.name, "sccfm_connectivity_state", str(device.connectivity_state)
        )
        self._inventory.set_variable(device.name, "sccfm_config_state", str(device.config_state))
        self._inventory.set_variable(device.name, "sccfm_software_version", device.software_version)
