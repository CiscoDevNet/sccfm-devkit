"""Tests for sccfm_core.services.inventory.asa_upgrade_version_service module."""

from __future__ import annotations

from scc_firewall_manager_sdk import AsaCompatibleVersion

from sccfm_core.services.inventory.asa_upgrade_version_service import (
    _compute_intersection,
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
