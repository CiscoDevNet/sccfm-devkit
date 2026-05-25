# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re

from sccfm_core.models.asa_failover_status import (
    AsaFailoverInterface,
    AsaFailoverStatus,
    AsaFailoverUnit,
)

# ── show failover patterns ───────────────────────────────────────

# "Failover On" or "Failover Off"
_FAILOVER_STATE_RE = re.compile(
    r"^Failover\s+(On|Off)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# "Failover unit Primary"
_FAILOVER_UNIT_RE = re.compile(
    r"^Failover unit\s+(\S+)",
    re.IGNORECASE | re.MULTILINE,
)

# "Failover LAN Interface: INTFC GigabitEthernet0/8 (up)"
_LAN_INTF_RE = re.compile(
    r"^Failover LAN Interface:\s+(\S+)\s+(\S+)\s+\((\w+)\)",
    re.IGNORECASE | re.MULTILINE,
)

# "Monitored Interfaces 3 of 110 maximum"
_MONITORED_RE = re.compile(
    r"^Monitored Interfaces\s+(\d+)\s+of\s+(\d+)",
    re.IGNORECASE | re.MULTILINE,
)

# "Version: Ours 9.20(3)10, Mate 9.20(3)10"
_VERSION_RE = re.compile(
    r"^Version:\s+Ours\s+(.+?),\s+Mate\s+(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# "Serial Number: Ours JAD251400QT, Mate 9AA77409PDA"
_SERIAL_RE = re.compile(
    r"^Serial Number:\s+Ours\s+(\S+),\s+Mate\s+(\S+)",
    re.IGNORECASE | re.MULTILINE,
)

# "Last Failover at: 14:23:15 UTC Jun 5 2024"
_LAST_FAILOVER_RE = re.compile(
    r"^Last Failover at:\s+(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# "        This host: Primary - Active"
_THIS_HOST_RE = re.compile(
    r"^\s+This host:\s+(\S+)\s+-\s+(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# "        Other host: Secondary - Standby Ready"
_OTHER_HOST_RE = re.compile(
    r"^\s+Other host:\s+(\S+)\s+-\s+(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# "                Active time: 12345 (sec)"
_ACTIVE_TIME_RE = re.compile(
    r"Active time:\s+(\d+)\s+\(sec\)",
    re.IGNORECASE,
)

# "                  Interface outside (10.0.0.1): Normal (Monitored)"
_INTERFACE_RE = re.compile(
    r"^\s+Interface\s+(\S+)\s+\(([^)]*)\):\s+(\S+)\s+\(([^)]+)\)",
    re.IGNORECASE | re.MULTILINE,
)

# ── show failover state patterns ─────────────────────────────────

# "====Configuration State===\n        Sync Done"
_CONFIG_STATE_RE = re.compile(
    r"={3,}Configuration State={3,}\s*\n\s+(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_failover_status(
    show_failover_output: str,
    show_failover_state_output: str = "",
) -> AsaFailoverStatus:
    """Parse ``show failover`` and ``show failover state`` output.

    Both inputs are raw text returned by the ASA CLI.  The second
    argument is optional; when omitted, ``config_sync_state`` falls
    back to ``"unknown"``.
    """
    failover_enabled = _is_failover_enabled(show_failover_output)
    failover_unit = _extract(_FAILOVER_UNIT_RE, show_failover_output, default="unknown")

    lan_match = _LAN_INTF_RE.search(show_failover_output)
    lan_interface_name = lan_match.group(1) if lan_match else "unknown"
    lan_hardware = lan_match.group(2) if lan_match else "unknown"
    lan_state = lan_match.group(3).lower() if lan_match else "unknown"

    version_match = _VERSION_RE.search(show_failover_output)
    version_ours = version_match.group(1) if version_match else "unknown"
    version_mate = version_match.group(2) if version_match else "unknown"

    serial_match = _SERIAL_RE.search(show_failover_output)
    serial_ours = serial_match.group(1) if serial_match else "unknown"
    serial_mate = serial_match.group(2) if serial_match else "unknown"

    monitored_match = _MONITORED_RE.search(show_failover_output)
    monitored_count = int(monitored_match.group(1)) if monitored_match else 0
    monitored_max = int(monitored_match.group(2)) if monitored_match else 0

    last_failover = _extract(_LAST_FAILOVER_RE, show_failover_output, default="unknown")

    this_host, other_host = _parse_host_sections(show_failover_output)

    # Config sync from show failover state, or from show failover if combined
    combined = show_failover_state_output or show_failover_output
    config_sync_state = _extract(_CONFIG_STATE_RE, combined, default="unknown")

    return AsaFailoverStatus(
        failover_enabled=failover_enabled,
        failover_unit=failover_unit,
        lan_interface_name=lan_interface_name,
        lan_hardware=lan_hardware,
        lan_state=lan_state,
        version_ours=version_ours,
        version_mate=version_mate,
        serial_ours=serial_ours,
        serial_mate=serial_mate,
        last_failover=last_failover,
        monitored_count=monitored_count,
        monitored_max=monitored_max,
        this_host=this_host,
        other_host=other_host,
        config_sync_state=config_sync_state,
    )


def _is_failover_enabled(text: str) -> bool:
    """Return True if ``show failover`` indicates failover is ON."""
    match = _FAILOVER_STATE_RE.search(text)
    return match.group(1).lower() == "on" if match else False


def _parse_host_sections(text: str) -> tuple[AsaFailoverUnit, AsaFailoverUnit]:
    """Extract This host and Other host sections with their interfaces."""
    this_match = _THIS_HOST_RE.search(text)
    other_match = _OTHER_HOST_RE.search(text)

    if not this_match or not other_match:
        empty = AsaFailoverUnit(role="unknown", state="unknown", active_time=0)
        return (
            _build_unit(this_match, text) if this_match else empty,
            _build_unit(other_match, text) if other_match else empty,
        )

    # Split the text at the Other host boundary to isolate each section
    this_section = text[this_match.start() : other_match.start()]
    other_section = text[other_match.start() :]

    return (
        _build_unit(this_match, this_section),
        _build_unit(other_match, other_section),
    )


def _build_unit(
    host_match: re.Match[str],
    section: str = "",
) -> AsaFailoverUnit:
    """Build an :class:`AsaFailoverUnit` from a host match and its text section."""
    role = host_match.group(1)
    state = host_match.group(2).strip()

    active_time_match = _ACTIVE_TIME_RE.search(section)
    active_time = int(active_time_match.group(1)) if active_time_match else 0

    interfaces = _parse_interfaces(section)

    return AsaFailoverUnit(
        role=role,
        state=state,
        active_time=active_time,
        interfaces=interfaces,
    )


def _parse_interfaces(section: str) -> list[AsaFailoverInterface]:
    """Parse interface lines from a host section."""
    interfaces: list[AsaFailoverInterface] = []
    for match in _INTERFACE_RE.finditer(section):
        interfaces.append(
            AsaFailoverInterface(
                name=match.group(1),
                ip_address=match.group(2),
                status=match.group(3),
                monitoring=match.group(4),
            )
        )
    return interfaces


def _extract(pattern: re.Pattern[str], text: str, *, default: str) -> str:
    """Return the first capture group from *pattern*, or *default*."""
    match = pattern.search(text)
    return match.group(1).strip() if match else default
