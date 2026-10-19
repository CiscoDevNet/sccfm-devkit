# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for cisco_sccfm_core.services.inventory.ftd_upgrade_version_service module."""

from __future__ import annotations

from scc_firewall_manager_sdk import FtdVersion

from cisco_sccfm_core.services.inventory.ftd_upgrade_version_service import (
    _compute_intersection,
    resolve_upgrade_package_uid,
)


def _v(sw: str, pkg_uid: str = "", upgrade_type: str = "UPGRADE") -> FtdVersion:
    return FtdVersion(
        softwareVersion=sw,
        upgradePackageUid=pkg_uid,
        upgradeType=upgrade_type,
        filename=f"{sw}.pkg",
        isSuggestedVersion=False,
    )


class TestComputeIntersection:
    """Tests for _compute_intersection()."""

    def test_should_return_empty_for_no_devices(self) -> None:
        assert _compute_intersection({}) == []

    def test_should_return_all_versions_for_single_device(self) -> None:
        per_device = {
            "uid-1": [_v("7.4.1", "pkg-1"), _v("7.2.5", "pkg-2")],
        }
        result = _compute_intersection(per_device)
        sw_versions = [v.software_version for v in result]
        assert sw_versions == ["7.4.1", "7.2.5"]

    def test_should_return_intersection_for_two_devices(self) -> None:
        per_device = {
            "uid-1": [_v("7.4.1", "pkg-1"), _v("7.2.5", "pkg-2"), _v("7.0.6", "pkg-3")],
            "uid-2": [_v("7.4.1", "pkg-4"), _v("7.0.6", "pkg-5")],
        }
        result = _compute_intersection(per_device)
        sw_versions = {v.software_version for v in result}
        assert sw_versions == {"7.4.1", "7.0.6"}

    def test_should_return_empty_when_no_overlap(self) -> None:
        per_device = {
            "uid-1": [_v("7.4.1")],
            "uid-2": [_v("7.2.5")],
        }
        assert _compute_intersection(per_device) == []

    def test_should_handle_three_devices(self) -> None:
        per_device = {
            "uid-1": [_v("7.4.1"), _v("7.2.5"), _v("7.0.6")],
            "uid-2": [_v("7.4.1"), _v("7.0.6"), _v("6.7.0")],
            "uid-3": [_v("7.4.1"), _v("7.0.6")],
        }
        result = _compute_intersection(per_device)
        sw_versions = {v.software_version for v in result}
        assert sw_versions == {"7.4.1", "7.0.6"}

    def test_should_use_first_device_objects_for_common_versions(self) -> None:
        """Common versions should carry the full object from the first device."""
        v1 = _v("7.4.1", "pkg-from-first")
        per_device = {
            "uid-1": [v1],
            "uid-2": [_v("7.4.1", "pkg-from-second")],
        }
        result = _compute_intersection(per_device)
        assert len(result) == 1
        assert result[0].upgrade_package_uid == "pkg-from-first"

    def test_should_skip_versions_with_none_software_version(self) -> None:
        per_device = {
            "uid-1": [_v("7.4.1", "pkg-1"), FtdVersion()],
            "uid-2": [_v("7.4.1", "pkg-2")],
        }
        result = _compute_intersection(per_device)
        assert len(result) == 1
        assert result[0].software_version == "7.4.1"


class TestResolveUpgradePackageUid:
    """Tests for resolve_upgrade_package_uid()."""

    def test_should_find_matching_version(self) -> None:
        versions = [_v("7.2.5", "pkg-a"), _v("7.4.1", "pkg-b")]
        assert resolve_upgrade_package_uid(versions, "7.4.1") == "pkg-b"

    def test_should_return_none_when_not_found(self) -> None:
        versions = [_v("7.2.5", "pkg-a"), _v("7.4.1", "pkg-b")]
        assert resolve_upgrade_package_uid(versions, "7.6.0") is None

    def test_should_return_none_for_empty_list(self) -> None:
        assert resolve_upgrade_package_uid([], "7.4.1") is None

    def test_should_match_exact_version_string(self) -> None:
        versions = [_v("7.4.1", "pkg-a"), _v("7.4.1.1", "pkg-b")]
        assert resolve_upgrade_package_uid(versions, "7.4.1") == "pkg-a"
