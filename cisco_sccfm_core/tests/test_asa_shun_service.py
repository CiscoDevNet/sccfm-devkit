# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for cisco_sccfm_core.services.inventory.asa_shun_service internals."""

from __future__ import annotations

from unittest.mock import MagicMock

from scc_firewall_manager_sdk import CdoCliResult

from cisco_sccfm_core.services.inventory.asa_shun_service import (
    AsaShunService,
    ShunEntrySpec,
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


class TestShunEntrySpec:
    """Tests for the ShunEntrySpec dataclass."""

    def test_source_ip_only(self) -> None:
        spec = ShunEntrySpec(source_ip="10.1.1.1")
        assert spec.source_ip == "10.1.1.1"
        assert spec.dest_ip is None
        assert spec.source_port is None
        assert spec.dest_port is None
        assert spec.protocol is None

    def test_full_spec(self) -> None:
        spec = ShunEntrySpec(
            source_ip="10.1.1.1",
            dest_ip="10.2.2.2",
            source_port=555,
            dest_port=443,
            protocol="tcp",
        )
        assert spec.dest_ip == "10.2.2.2"
        assert spec.source_port == 555
        assert spec.dest_port == 443
        assert spec.protocol == "tcp"


class TestAddShunEntries:
    """Tests for AsaShunService.add_shun_entries."""

    def test_single_entry_delegates_to_cli(self) -> None:
        service = AsaShunService.__new__(AsaShunService)
        service._cli_service = MagicMock()
        service._cli_service.execute_cli.return_value = []

        service.add_shun_entries(
            device_uids=["dev-1"],
            entries=[ShunEntrySpec(source_ip="10.1.1.1")],
        )

        service._cli_service.execute_cli.assert_called_once_with(
            device_uids=["dev-1"],
            asa_commands=["shun 10.1.1.1"],
            wait=True,
        )

    def test_multiple_entries_sent_as_one_call(self) -> None:
        service = AsaShunService.__new__(AsaShunService)
        service._cli_service = MagicMock()
        service._cli_service.execute_cli.return_value = []

        service.add_shun_entries(
            device_uids=["dev-1"],
            entries=[
                ShunEntrySpec(source_ip="10.1.1.1"),
                ShunEntrySpec(
                    source_ip="20.2.2.2",
                    dest_ip="10.3.3.3",
                    source_port=555,
                    dest_port=443,
                    protocol="tcp",
                ),
            ],
        )

        service._cli_service.execute_cli.assert_called_once_with(
            device_uids=["dev-1"],
            asa_commands=["shun 10.1.1.1", "shun 20.2.2.2 10.3.3.3 555 443 tcp"],
            wait=True,
        )

    def test_add_shun_delegates_to_add_shun_entries(self) -> None:
        service = AsaShunService.__new__(AsaShunService)
        service._cli_service = MagicMock()
        service._cli_service.execute_cli.return_value = []

        service.add_shun(device_uids=["dev-1"], source_ip="10.1.1.1")

        service._cli_service.execute_cli.assert_called_once_with(
            device_uids=["dev-1"],
            asa_commands=["shun 10.1.1.1"],
            wait=True,
        )


class TestRemoveShunEntries:
    """Tests for AsaShunService.remove_shun_entries."""

    def test_single_ip_delegates_to_cli(self) -> None:
        service = AsaShunService.__new__(AsaShunService)
        service._cli_service = MagicMock()
        service._cli_service.execute_cli.return_value = []

        service.remove_shun_entries(device_uids=["dev-1"], source_ips=["10.1.1.1"])

        service._cli_service.execute_cli.assert_called_once_with(
            device_uids=["dev-1"],
            asa_commands=["no shun 10.1.1.1"],
            wait=True,
        )

    def test_multiple_ips_sent_as_one_call(self) -> None:
        service = AsaShunService.__new__(AsaShunService)
        service._cli_service = MagicMock()
        service._cli_service.execute_cli.return_value = []

        service.remove_shun_entries(
            device_uids=["dev-1"],
            source_ips=["10.1.1.1", "10.2.2.2", "10.3.3.3"],
        )

        service._cli_service.execute_cli.assert_called_once_with(
            device_uids=["dev-1"],
            asa_commands=["no shun 10.1.1.1", "no shun 10.2.2.2", "no shun 10.3.3.3"],
            wait=True,
        )

    def test_remove_shun_delegates_to_remove_shun_entries(self) -> None:
        service = AsaShunService.__new__(AsaShunService)
        service._cli_service = MagicMock()
        service._cli_service.execute_cli.return_value = []

        service.remove_shun(device_uids=["dev-1"], source_ip="10.1.1.1")

        service._cli_service.execute_cli.assert_called_once_with(
            device_uids=["dev-1"],
            asa_commands=["no shun 10.1.1.1"],
            wait=True,
        )
