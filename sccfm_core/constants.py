from __future__ import annotations

from scc_firewall_manager_sdk import EntityType

FTD_ENTITY_TYPES = [
    EntityType.CDFMC_MANAGED_FTD,
    EntityType.FDM_MANAGED_FTD,
    EntityType.ONPREM_FMC_MANAGED_FTD,
]

FTD_LICENSES = ["BASE", "CARRIER", "THREAT", "MALWARE", "URLFilter"]

FTDV_PERFORMANCE_TIERS = ["FTDv5", "FTDv10", "FTDv20", "FTDv30", "FTDv50", "FTDv100", "FTDv"]
