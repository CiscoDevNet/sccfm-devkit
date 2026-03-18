"""Tests for sccfm_core.services.inventory.asa_shun_service internals."""

from __future__ import annotations

from scc_firewall_manager_sdk import CdoCliResult

from sccfm_core.services.inventory.asa_shun_service import (
    _build_shun_command,
    _parse_shun_entries,
    _parse_shun_stats,
)

_SHOW_SHUN_TWO_ENTRIES = (
    "shun (outside) 10.1.1.27 10.2.2.89 555 666 6\n" "shun (inside) 192.168.1.50 0.0.0.0 0 0 0\n"
)

_SHOW_SHUN_EMPTY = ""

_SHOW_SHUN_STATISTICS = (
    "outside=gilligan 0 Shunned, 10 received\n" "inside=mary_ann 5 Shunned, 100 received\n"
)


class TestParseShunEntries:
    """Tests for _parse_shun_entries."""

    def test_single_device_with_entries(self) -> None:
        results = [
            CdoCliResult(
                uid="r1", device_uid="dev-1", result=_SHOW_SHUN_TWO_ENTRIES, script="show shun"
            ),
        ]
        parsed = _parse_shun_entries(results)
        assert "dev-1" in parsed
        assert len(parsed["dev-1"]) == 2
        assert parsed["dev-1"][0].source_ip == "10.1.1.27"

    def test_single_device_no_entries(self) -> None:
        results = [
            CdoCliResult(uid="r1", device_uid="dev-1", result=_SHOW_SHUN_EMPTY, script="show shun"),
        ]
        parsed = _parse_shun_entries(results)
        assert parsed["dev-1"] == []

    def test_multiple_devices(self) -> None:
        results = [
            CdoCliResult(
                uid="r1", device_uid="dev-1", result=_SHOW_SHUN_TWO_ENTRIES, script="show shun"
            ),
            CdoCliResult(uid="r2", device_uid="dev-2", result=_SHOW_SHUN_EMPTY, script="show shun"),
        ]
        parsed = _parse_shun_entries(results)
        assert len(parsed) == 2
        assert len(parsed["dev-1"]) == 2
        assert parsed["dev-2"] == []

    def test_none_result_treated_as_empty(self) -> None:
        results = [
            CdoCliResult(uid="r1", device_uid="dev-1", result=None, script="show shun"),
        ]
        parsed = _parse_shun_entries(results)
        assert parsed["dev-1"] == []


class TestParseShunStats:
    """Tests for _parse_shun_stats."""

    def test_single_device_with_stats(self) -> None:
        results = [
            CdoCliResult(
                uid="r1",
                device_uid="dev-1",
                result=_SHOW_SHUN_STATISTICS,
                script="show shun statistics",
            ),
        ]
        parsed = _parse_shun_stats(results)
        assert len(parsed["dev-1"]) == 2
        assert parsed["dev-1"][0].interface == "outside"
        assert parsed["dev-1"][0].received == 10

    def test_single_device_no_stats(self) -> None:
        results = [
            CdoCliResult(
                uid="r1", device_uid="dev-1", result=_SHOW_SHUN_EMPTY, script="show shun statistics"
            ),
        ]
        parsed = _parse_shun_stats(results)
        assert parsed["dev-1"] == []

    def test_none_result_treated_as_empty(self) -> None:
        results = [
            CdoCliResult(uid="r1", device_uid="dev-1", result=None, script="show shun statistics"),
        ]
        parsed = _parse_shun_stats(results)
        assert parsed["dev-1"] == []


class TestBuildShunCommand:
    """Tests for the _build_shun_command helper."""

    def test_source_ip_only(self) -> None:
        cmd = _build_shun_command(
            source_ip="10.1.1.27", dest_ip=None, source_port=None, dest_port=None, protocol=None
        )
        assert cmd == "shun 10.1.1.27"

    def test_full_connection_tuple_with_protocol(self) -> None:
        cmd = _build_shun_command(
            source_ip="10.1.1.27",
            dest_ip="10.2.2.89",
            source_port=555,
            dest_port=666,
            protocol="tcp",
        )
        assert cmd == "shun 10.1.1.27 10.2.2.89 555 666 tcp"

    def test_connection_tuple_without_protocol(self) -> None:
        cmd = _build_shun_command(
            source_ip="10.1.1.27",
            dest_ip="10.2.2.89",
            source_port=555,
            dest_port=666,
            protocol=None,
        )
        assert cmd == "shun 10.1.1.27 10.2.2.89 555 666"

    def test_connection_tuple_defaults_ports_to_zero(self) -> None:
        cmd = _build_shun_command(
            source_ip="10.1.1.27",
            dest_ip="10.2.2.89",
            source_port=None,
            dest_port=None,
            protocol=None,
        )
        assert cmd == "shun 10.1.1.27 10.2.2.89 0 0"
