from __future__ import annotations

from collections.abc import Sequence

from scc_firewall_manager_sdk import EntityType

SCCFM_REGIONS = ("int", "us", "eu", "apj", "au", "uae", "in", "ci")
SCCFM_REGION_ALIASES = {"aus": "au"}
SCCFM_REGION_CHOICES = SCCFM_REGIONS + tuple(SCCFM_REGION_ALIASES)


def normalize_sccfm_region(region: str | None) -> str | None:
    """Normalize region input to the canonical SCCFM region value."""
    if region is None:
        return None

    normalized = region.strip().lower()
    if not normalized:
        return ""

    return SCCFM_REGION_ALIASES.get(normalized, normalized)


ASA_ENTITY_TYPES = [
    EntityType.ASA,
]

FTD_ENTITY_TYPES = [
    EntityType.CDFMC_MANAGED_FTD,
    EntityType.FDM_MANAGED_FTD,
    EntityType.ONPREM_FMC_MANAGED_FTD,
]


def build_device_type_filter(entity_types: Sequence[EntityType]) -> str:
    """Build a Lucene device-type filter from one or more entity types."""
    if len(entity_types) == 1:
        return f"deviceType:{entity_types[0].value}"

    clause = " OR ".join(f"deviceType:{entity_type.value}" for entity_type in entity_types)
    return f"({clause})"


ASA_DEVICE_TYPE_FILTER = build_device_type_filter(ASA_ENTITY_TYPES)
FTD_DEVICE_TYPE_FILTER = build_device_type_filter(FTD_ENTITY_TYPES)

FTD_LICENSES = ["BASE", "CARRIER", "THREAT", "MALWARE", "URLFilter"]

FTDV_PERFORMANCE_TIERS = ["FTDv5", "FTDv10", "FTDv20", "FTDv30", "FTDv50", "FTDv100", "FTDv"]

# --- Async transaction policy --------------------------------------------------
# These constants are the single source of truth for how long the CLI, the
# Ansible collection, and the core service layer wait for asynchronous
# transactions to finish, and how often they poll for status. Callers should
# import these instead of hard-coding magic numbers so behavior stays aligned
# across surfaces.

DEFAULT_TRANSACTION_TIMEOUT_SEC = 3600
"""Default user-facing wait time for a single long-running transaction."""

DEFAULT_POLLING_INTERVAL_SEC = 10
"""Base polling cadence used by the transaction service when callers do not
override it. Suitable for most management-plane operations."""

ONBOARD_POLLING_INTERVAL_SEC = 5
"""Polling cadence for onboarding flows where transactions complete on the
order of seconds-to-minutes and benefit from snappier feedback."""

FAST_POLLING_INTERVAL_SEC = 3
"""Polling cadence for fast interactive flows such as ASA CLI execution where
end-to-end latency dominates user experience."""
