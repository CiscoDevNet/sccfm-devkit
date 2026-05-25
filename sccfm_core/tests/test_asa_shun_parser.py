# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for sccfm_core.parsers.asa_shun_parser module."""

from __future__ import annotations

from sccfm_core.models.asa_shun_entry import AsaShunEntry, AsaShunInterfaceStats
from sccfm_core.parsers.asa_shun_parser import parse_shun_entries, parse_shun_statistics

SAMPLE_SINGLE_ENTRY = """\
shun (outside) 10.1.1.27 10.2.2.89 555 666 6
"""

SAMPLE_MULTIPLE_ENTRIES = """\
shun (outside) 10.1.1.27 10.2.2.89 555 666 6
shun (inside) 192.168.1.50 0.0.0.0 0 0 0
shun (dmz) 172.16.0.5 10.10.10.10 80 8080 17
"""

SAMPLE_WITH_NOISE = """\
Shun Tree:
shun (outside) 10.1.1.27 10.2.2.89 555 666 6
some other output line
shun (inside) 192.168.1.50 0.0.0.0 0 0 0
"""

SAMPLE_STATISTICS = """\
Shun Statistics
outside=gilligan 0 Shunned, 10 received
inside=mary_ann 5 Shunned, 100 received
"""

SAMPLE_STATISTICS_SINGLE = """\
outside=outside 3 Shunned, 42 received
"""


class TestParseShunEntries:
    """Tests for parse_shun_entries()."""

    def test_should_parse_single_entry(self) -> None:
        entries = parse_shun_entries(SAMPLE_SINGLE_ENTRY)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.interface == "outside"
        assert entry.source_ip == "10.1.1.27"
        assert entry.destination_ip == "10.2.2.89"
        assert entry.source_port == 555
        assert entry.destination_port == 666
        assert entry.protocol == 6

    def test_should_parse_multiple_entries(self) -> None:
        entries = parse_shun_entries(SAMPLE_MULTIPLE_ENTRIES)
        assert len(entries) == 3
        assert entries[0].interface == "outside"
        assert entries[0].protocol == 6
        assert entries[1].interface == "inside"
        assert entries[1].source_ip == "192.168.1.50"
        assert entries[1].protocol == 0
        assert entries[2].interface == "dmz"
        assert entries[2].protocol == 17

    def test_should_skip_noise_lines(self) -> None:
        entries = parse_shun_entries(SAMPLE_WITH_NOISE)
        assert len(entries) == 2
        assert entries[0].source_ip == "10.1.1.27"
        assert entries[1].source_ip == "192.168.1.50"

    def test_should_return_empty_for_no_entries(self) -> None:
        assert parse_shun_entries("No shun entries found.\n") == []

    def test_should_return_empty_for_empty_string(self) -> None:
        assert parse_shun_entries("") == []

    def test_should_return_frozen_dataclass_instances(self) -> None:
        entries = parse_shun_entries(SAMPLE_SINGLE_ENTRY)
        assert isinstance(entries[0], AsaShunEntry)
        try:
            entries[0].source_ip = "changed"  # type: ignore[misc,unused-ignore]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass

    def test_should_parse_zero_ports_and_protocol(self) -> None:
        output = "shun (inside) 192.168.1.50 0.0.0.0 0 0 0\n"
        entries = parse_shun_entries(output)
        assert len(entries) == 1
        assert entries[0].source_port == 0
        assert entries[0].destination_port == 0
        assert entries[0].protocol == 0


class TestParseShunStatistics:
    """Tests for parse_shun_statistics()."""

    def test_should_parse_multiple_interfaces(self) -> None:
        stats = parse_shun_statistics(SAMPLE_STATISTICS)
        assert len(stats) == 2
        assert stats[0].interface == "outside"
        assert stats[0].shunned == 0
        assert stats[0].received == 10
        assert stats[1].interface == "inside"
        assert stats[1].shunned == 5
        assert stats[1].received == 100

    def test_should_parse_single_interface(self) -> None:
        stats = parse_shun_statistics(SAMPLE_STATISTICS_SINGLE)
        assert len(stats) == 1
        assert stats[0].interface == "outside"
        assert stats[0].shunned == 3
        assert stats[0].received == 42

    def test_should_return_empty_for_no_stats(self) -> None:
        assert parse_shun_statistics("") == []
        assert parse_shun_statistics("Shun Statistics\n") == []

    def test_should_return_frozen_dataclass_instances(self) -> None:
        stats = parse_shun_statistics(SAMPLE_STATISTICS_SINGLE)
        assert isinstance(stats[0], AsaShunInterfaceStats)
        try:
            stats[0].shunned = 999  # type: ignore[misc,unused-ignore]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass
