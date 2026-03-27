from __future__ import annotations

from typing import Sequence

from scc_firewall_manager_sdk import EntityType

from sccfm_cli.commands.inventory.devices.rendering import DeviceListCommand


class CdfmcFtdListCommand(DeviceListCommand):
    @property
    def help_text(self) -> str:
        return "List cdFMC-managed FTD devices."

    @property
    def entity_types(self) -> Sequence[EntityType]:
        return [EntityType.CDFMC_MANAGED_FTD]

    @property
    def spinner_text(self) -> str:
        return "Fetching cdFMC-managed FTD devices from SCC Firewall Manager..."
