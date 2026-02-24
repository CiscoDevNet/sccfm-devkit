from __future__ import annotations

from functools import reduce

from scc_firewall_manager_sdk import AsaCompatibleVersion, DeviceUpgradesApi

from sccfm_core.factories import ApiClientFactory
from sccfm_core.models.asa_upgrade_version import AsaGroupCompatibleVersions
from sccfm_core.types import ConfigLike
from sccfm_core.utils import validate_uids


class AsaUpgradeVersionService:
    """Retrieves compatible upgrade versions for a group of ASA devices."""

    def __init__(self, config: ConfigLike) -> None:
        self._upgrades_api = DeviceUpgradesApi(ApiClientFactory().build(config=config))

    def get_compatible_versions(self, device_uids: list[str]) -> AsaGroupCompatibleVersions:
        """Fetch compatible versions per device and compute the common set.

        The intersection is determined by ``software_version`` — a version
        is "common" only when its ``software_version`` string appears in
        every device's compatible-version list.
        """
        validate_uids(device_uids)

        per_device: dict[str, list[AsaCompatibleVersion]] = {}
        for uid in device_uids:
            response = self._upgrades_api.get_asa_upgrade_versions(device_uid=uid)
            per_device[uid] = list(response.items or [])

        common = _compute_intersection(per_device)
        return AsaGroupCompatibleVersions(per_device=per_device, common_versions=common)


def _compute_intersection(
    per_device: dict[str, list[AsaCompatibleVersion]],
) -> list[AsaCompatibleVersion]:
    """Return versions whose software_version appears in every device's list."""
    if not per_device:
        return []

    version_sets = [
        {v.software_version for v in versions if v.software_version}
        for versions in per_device.values()
    ]
    common_sw_versions: set[str] = reduce(set.intersection, version_sets)

    first_device_versions = next(iter(per_device.values()))
    return [v for v in first_device_versions if v.software_version in common_sw_versions]
