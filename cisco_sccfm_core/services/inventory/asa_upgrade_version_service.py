# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce

from scc_firewall_manager_sdk import AsaCompatibleVersion, DeviceUpgradesApi

from cisco_sccfm_core.factories import ApiClientFactory
from cisco_sccfm_core.models.asa_upgrade_version import AsaGroupCompatibleVersions
from cisco_sccfm_core.types import ConfigLike
from cisco_sccfm_core.utils import validate_uids


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


@dataclass(frozen=True)
class AsdmCompatibilityInfo:
    """ASDM versions compatible with a specific ASA software version.

    ``compatible_asdm_versions`` is the full set of ASDM versions that
    can be paired with the target software version.
    ``minimum_asdm_version`` is the lowest version string
    (lexicographic sort after normalising Cisco version tuples).
    """

    compatible_asdm_versions: set[str]
    minimum_asdm_version: str


def get_asdm_compatibility_info(
    compatible_versions: list[AsaCompatibleVersion],
    software_version: str,
) -> AsdmCompatibilityInfo | None:
    """Return ASDM compatibility info for *software_version*, or ``None``.

    Collects every ``asdm_version`` paired with *software_version* in
    the compatible-versions list and determines the minimum.
    """
    asdm_set: set[str] = set()
    for v in compatible_versions:
        if v.software_version == software_version and v.asdm_version:
            asdm_set.add(v.asdm_version)

    if not asdm_set:
        return None

    minimum = min(asdm_set, key=_version_sort_key)
    return AsdmCompatibilityInfo(
        compatible_asdm_versions=asdm_set,
        minimum_asdm_version=minimum,
    )


def _version_sort_key(version: str) -> tuple[tuple[int, ...], str]:
    """Sort key for Cisco version strings like ``7.6(1)`` or ``7.18(1.152).openjre``.

    Returns a tuple of (numeric_parts, suffix) so that ``7.6(1)`` sorts
    before ``7.18(1.152)`` and plain versions sort before suffixed ones.
    """
    import re

    nums = tuple(int(n) for n in re.findall(r"\d+", version))
    # Strip all numeric/separator chars to get the trailing suffix (e.g. ".openjre")
    suffix = re.sub(r"[\d.()]+", "", version)
    return (nums, suffix)


def is_version_downgrade(target: str, current: str) -> bool:
    """Return ``True`` if *target* is strictly lower than *current*."""
    return _version_sort_key(target) < _version_sort_key(current)
