# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from typing import List

from sccfm_core.models.asa_shun_entry import AsaShunEntry, AsaShunInterfaceStats

# Matches a shun entry line from ``show shun`` output.
#
# Examples::
#
#   shun (outside) 10.1.1.27 10.2.2.89 555 666 6
#   shun (inside) 192.168.1.50 0.0.0.0 0 0 0
_SHUN_LINE_RE = re.compile(
    r"^\s*shun\s+"
    r"\((\S+)\)\s+"  # interface name (group 1)
    r"(\d{1,3}(?:\.\d{1,3}){3})\s+"  # source IP (group 2)
    r"(\d{1,3}(?:\.\d{1,3}){3})\s+"  # destination IP (group 3)
    r"(\d+)\s+"  # source port (group 4)
    r"(\d+)\s+"  # destination port (group 5)
    r"(\d+)"  # protocol number (group 6)
)

# Matches per-interface statistics from ``show shun statistics``.
#
# Examples::
#
#   outside=gilligan 0 Shunned, 10 received
#   inside=mary_ann 5 Shunned, 100 received
_INTF_STATS_RE = re.compile(
    r"^\s*(\S+?)=\S+\s+"  # interface name (group 1), skip nameif alias
    r"(\d+)\s+Shunned,\s+"  # shunned count (group 2)
    r"(\d+)\s+received"  # received count (group 3)
)


def parse_shun_entries(raw_output: str) -> List[AsaShunEntry]:
    """Parse the output of ``show shun`` into a list of shun entries.

    Returns an empty list when no shun entries are present.
    """
    entries: List[AsaShunEntry] = []
    for line in raw_output.splitlines():
        match = _SHUN_LINE_RE.match(line)
        if match:
            interface, src_ip, dst_ip, src_port, dst_port, protocol = match.groups()
            entries.append(
                AsaShunEntry(
                    interface=interface,
                    source_ip=src_ip,
                    destination_ip=dst_ip,
                    source_port=int(src_port),
                    destination_port=int(dst_port),
                    protocol=int(protocol),
                )
            )
    return entries


def parse_shun_statistics(raw_output: str) -> List[AsaShunInterfaceStats]:
    """Parse the output of ``show shun statistics``.

    Extracts per-interface shun/received counters. Returns an empty
    list when no statistics lines are found.
    """
    stats: List[AsaShunInterfaceStats] = []
    for line in raw_output.splitlines():
        match = _INTF_STATS_RE.match(line)
        if match:
            interface, shunned, received = match.groups()
            stats.append(
                AsaShunInterfaceStats(
                    interface=interface,
                    shunned=int(shunned),
                    received=int(received),
                )
            )
    return stats
