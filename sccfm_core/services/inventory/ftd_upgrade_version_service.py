from __future__ import annotations

from functools import reduce

from scc_firewall_manager_sdk import ApiException, DeviceUpgradesApi, FtdVersion

from sccfm_core.errors import SccApiError
from sccfm_core.factories import ApiClientFactory
from sccfm_core.models.ftd_upgrade_version import FtdGroupCompatibleVersions
from sccfm_core.services.inventory.asa_upgrade_version_service import (
    _version_sort_key,
    is_version_downgrade,
)
from sccfm_core.types import ConfigLike
from sccfm_core.utils import validate_uids


class FtdUpgradeVersionService:
    """Retrieves compatible upgrade versions for a group of FTD devices."""

    def __init__(self, config: ConfigLike) -> None:
        self._upgrades_api = DeviceUpgradesApi(ApiClientFactory().build(config=config))

    def get_compatible_versions(self, device_uids: list[str]) -> FtdGroupCompatibleVersions:
        """Fetch compatible versions per device and compute the common set.

        The intersection is determined by ``software_version`` — a version
        is "common" only when its ``software_version`` string appears in
        every device's compatible-version list.

        Devices that the API rejects (e.g. unsupported device type) are
        collected in ``skipped`` rather than aborting the whole request.
        """
        validate_uids(device_uids)

        per_device: dict[str, list[FtdVersion]] = {}
        skipped: dict[str, str] = {}
        for uid in device_uids:
            try:
                response = self._upgrades_api.get_compatible_ftd_versions(device_uid=uid)
                per_device[uid] = list(response.items or [])
            except ApiException as exc:
                error = SccApiError.from_exception(exc)
                skipped[uid] = error.message

        common = _compute_intersection(per_device)
        return FtdGroupCompatibleVersions(
            per_device=per_device, common_versions=common, skipped=skipped
        )


def resolve_upgrade_package_uid(
    compatible_versions: list[FtdVersion],
    software_version: str,
) -> str | None:
    """Find the ``upgrade_package_uid`` for a given software version.

    Returns ``None`` if the version is not found in the compatible list.
    """
    for v in compatible_versions:
        if v.software_version == software_version:
            return v.upgrade_package_uid
    return None


def _compute_intersection(
    per_device: dict[str, list[FtdVersion]],
) -> list[FtdVersion]:
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
