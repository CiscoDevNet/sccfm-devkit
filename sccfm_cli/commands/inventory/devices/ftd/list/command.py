from __future__ import annotations

from typing import Sequence

from scc_firewall_manager_sdk import EntityType

from sccfm_cli.commands.inventory.devices.ftd.constants import FTD_ENTITY_TYPES
from sccfm_cli.commands.inventory.devices.rendering import DeviceListCommand


class FtdListCommand(DeviceListCommand):
    @property
    def help_text(self) -> str:
        return (
            "List FTD devices (includes cdFMC-managed, FDM-managed, "
            "and on-prem FMC-managed FTDs)."
        )

    @property
    def entity_types(self) -> Sequence[EntityType]:
        return FTD_ENTITY_TYPES

    @property
    def spinner_text(self) -> str:
        return "Fetching FTD devices from SCC Firewall Manager..."
