from __future__ import annotations

from typing import Sequence

from scc_firewall_manager_sdk import EntityType

from sccfm_cli.commands.inventory.devices.rendering import DeviceListCommand


class AsaListCommand(DeviceListCommand):
    @property
    def help_text(self) -> str:
        return "List ASA devices."

    @property
    def entity_types(self) -> Sequence[EntityType]:
        return [EntityType.ASA]

    @property
    def spinner_text(self) -> str:
        return "Fetching ASA devices from SCC Firewall Manager..."
