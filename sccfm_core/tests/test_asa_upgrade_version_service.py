# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for sccfm_core.services.inventory.asa_upgrade_version_service module."""

from __future__ import annotations

from scc_firewall_manager_sdk import AsaCompatibleVersion

from sccfm_core.services.inventory.asa_upgrade_version_service import (
    _compute_intersection,
    _version_sort_key,
    get_asdm_compatibility_info,
    is_version_downgrade,
)


def _v(sw: str, asdm: str = "") -> AsaCompatibleVersion:
    return AsaCompatibleVersion(softwareVersion=sw, asdmVersion=asdm)


class TestComputeIntersection:
    """Tests for _compute_intersection()."""

    def test_should_return_empty_for_no_devices(self) -> None:
        assert _compute_intersection({}) == []

    def test_should_return_all_versions_for_single_device(self) -> None:
        per_device = {
            "uid-1": [_v("9.18.4", "7.18"), _v("9.16.4", "7.16")],
        }
        result = _compute_intersection(per_device)
        sw_versions = [v.software_version for v in result]
        assert sw_versions == ["9.18.4", "9.16.4"]

    def test_should_return_intersection_for_two_devices(self) -> None:
        per_device = {
            "uid-1": [_v("9.18.4", "7.18"), _v("9.16.4", "7.16"), _v("9.14.4", "7.14")],
            "uid-2": [_v("9.18.4", "7.18"), _v("9.14.4", "7.14")],
        }
        result = _compute_intersection(per_device)
        sw_versions = {v.software_version for v in result}
        assert sw_versions == {"9.18.4", "9.14.4"}

    def test_should_return_empty_when_no_overlap(self) -> None:
        per_device = {
            "uid-1": [_v("9.18.4")],
            "uid-2": [_v("9.16.4")],
        }
        assert _compute_intersection(per_device) == []

    def test_should_handle_three_devices(self) -> None:
        per_device = {
            "uid-1": [_v("9.18.4"), _v("9.16.4"), _v("9.14.4")],
            "uid-2": [_v("9.18.4"), _v("9.14.4"), _v("9.12.4")],
            "uid-3": [_v("9.18.4"), _v("9.14.4")],
        }
        result = _compute_intersection(per_device)
        sw_versions = {v.software_version for v in result}
        assert sw_versions == {"9.18.4", "9.14.4"}

    def test_should_use_first_device_objects_for_common_versions(self) -> None:
        """Common versions should carry the full object from the first device."""
        v1 = _v("9.18.4", "7.18")
        per_device = {
            "uid-1": [v1],
            "uid-2": [_v("9.18.4", "7.18-different")],
        }
        result = _compute_intersection(per_device)
        assert len(result) == 1
        assert result[0].asdm_version == "7.18"

    def test_should_skip_versions_with_none_software_version(self) -> None:
        per_device = {
            "uid-1": [_v("9.18.4"), AsaCompatibleVersion()],
            "uid-2": [_v("9.18.4")],
        }
        result = _compute_intersection(per_device)
        assert len(result) == 1
        assert result[0].software_version == "9.18.4"


class TestGetAsdmCompatibilityInfo:
    """Tests for get_asdm_compatibility_info()."""

    def test_should_return_none_when_sw_version_not_found(self) -> None:
        versions = [_v("9.18.4", "7.18"), _v("9.16.4", "7.16")]
        assert get_asdm_compatibility_info(versions, "9.14.4") is None

    def test_should_return_none_for_empty_list(self) -> None:
        assert get_asdm_compatibility_info([], "9.18.4") is None

    def test_should_collect_all_asdm_versions_for_sw_version(self) -> None:
        versions = [
            _v("9.4(3)", "7.6(1)"),
            _v("9.4(3)", "7.7(1)"),
            _v("9.4(3)", "7.8(2)"),
            _v("9.4(2)", "7.5(2)"),
        ]
        info = get_asdm_compatibility_info(versions, "9.4(3)")
        assert info is not None
        assert info.compatible_asdm_versions == {"7.6(1)", "7.7(1)", "7.8(2)"}

    def test_should_compute_minimum_asdm_version(self) -> None:
        versions = [
            _v("9.4(3)", "7.18(1.152)"),
            _v("9.4(3)", "7.6(1)"),
            _v("9.4(3)", "7.24(1)"),
            _v("9.4(3)", "7.9(2)"),
        ]
        info = get_asdm_compatibility_info(versions, "9.4(3)")
        assert info is not None
        assert info.minimum_asdm_version == "7.6(1)"

    def test_should_prefer_non_openjre_as_minimum(self) -> None:
        versions = [
            _v("9.4(3)", "7.6(1)"),
            _v("9.4(3)", "7.6(1).openjre"),
        ]
        info = get_asdm_compatibility_info(versions, "9.4(3)")
        assert info is not None
        assert info.minimum_asdm_version == "7.6(1)"

    def test_should_include_openjre_in_compatible_set(self) -> None:
        versions = [
            _v("9.4(3)", "7.6(1)"),
            _v("9.4(3)", "7.6(1).openjre"),
        ]
        info = get_asdm_compatibility_info(versions, "9.4(3)")
        assert info is not None
        assert "7.6(1).openjre" in info.compatible_asdm_versions

    def test_should_skip_entries_with_none_asdm(self) -> None:
        versions = [
            _v("9.4(3)", "7.6(1)"),
            AsaCompatibleVersion(softwareVersion="9.4(3)"),
        ]
        info = get_asdm_compatibility_info(versions, "9.4(3)")
        assert info is not None
        assert info.compatible_asdm_versions == {"7.6(1)"}

    def test_should_match_exact_version_string(self) -> None:
        versions = [_v("9.4(2)", "7.5(2)"), _v("9.4(3)", "7.6(1)")]
        assert get_asdm_compatibility_info(versions, "9.4") is None


class TestCiscoVersionSortKey:
    """Tests for _version_sort_key()."""

    def test_should_sort_major_minor_correctly(self) -> None:
        versions = ["7.18(1)", "7.6(1)", "7.24(1)", "7.9(2)"]
        result = sorted(versions, key=_version_sort_key)
        assert result == ["7.6(1)", "7.9(2)", "7.18(1)", "7.24(1)"]

    def test_should_sort_openjre_after_plain(self) -> None:
        versions = ["7.6(1).openjre", "7.6(1)"]
        result = sorted(versions, key=_version_sort_key)
        assert result == ["7.6(1)", "7.6(1).openjre"]

    def test_should_sort_subversions_correctly(self) -> None:
        versions = ["7.18(1.152)", "7.18(1.150)", "7.18(1)"]
        result = sorted(versions, key=_version_sort_key)
        assert result == ["7.18(1)", "7.18(1.150)", "7.18(1.152)"]


class TestIsCiscoVersionDowngrade:
    """Tests for is_version_downgrade()."""

    def test_should_detect_downgrade(self) -> None:
        assert is_version_downgrade("7.5(2)", "7.20(2)") is True

    def test_should_not_flag_upgrade(self) -> None:
        assert is_version_downgrade("7.24(1)", "7.20(2)") is False

    def test_should_not_flag_same_version(self) -> None:
        assert is_version_downgrade("7.20(2)", "7.20(2)") is False

    def test_should_detect_subversion_downgrade(self) -> None:
        assert is_version_downgrade("7.18(1.150)", "7.18(1.152)") is True
