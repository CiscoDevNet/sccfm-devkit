# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for cisco_sccfm_core.parsers.asa_failover_parser module."""

from __future__ import annotations

from cisco_sccfm_core.models.asa_failover_status import (
    AsaFailoverInterface,
    AsaFailoverStatus,
    AsaFailoverUnit,
)
from cisco_sccfm_core.parsers.asa_failover_parser import parse_failover_status

# ── Sample data ──────────────────────────────────────────────────

SAMPLE_HEALTHY = """\
Failover On
Failover unit Primary
Failover LAN Interface: INTFC GigabitEthernet0/8 (up)
Reconnect timeout 0:00:00
Unit Poll frequency 1 seconds, holdtime 15 seconds
Interface Poll frequency 5 seconds, holdtime 25 seconds
Interface Policy 1
Monitored Interfaces 3 of 110 maximum
MAC Address Move Notification Interval not set
Version: Ours 9.20(3)10, Mate 9.20(3)10
Serial Number: Ours JAD251400QT, Mate 9AA77409PDA
Last Failover at: 14:23:15 UTC Jun 5 2024
        This host: Primary - Active
                Active time: 12345 (sec)
                slot 0: ASAv hw/sw rev (1.0/9.20(3)10) status (Up Sys)
                  Interface outside (10.0.0.1): Normal (Monitored)
                  Interface inside (192.168.1.1): Normal (Monitored)
                  Interface management (10.0.1.1): Normal (Monitored)
                  Interface diagnostic (0.0.0.0): Normal (Waiting)
                slot 1: empty
        Other host: Secondary - Standby Ready
                Active time: 0 (sec)
                slot 0: ASAv hw/sw rev (1.0/9.20(3)10) status (Up Sys)
                  Interface outside (10.0.0.2): Normal (Monitored)
                  Interface inside (192.168.1.2): Normal (Monitored)
                  Interface management (10.0.1.2): Normal (Monitored)
                  Interface diagnostic (0.0.0.0): Normal (Waiting)
                slot 1: empty

Stateful Failover Logical Update Statistics
        Link : stateful GigabitEthernet0/7 (up)
        Stateful Obj    xmit       xerr       rcv        rerr
        General         12345      0          12345      0
        sys cmd         6789       0          6789       0
"""

SAMPLE_FAILOVER_STATE = """\
               State          Last Failure Reason      Date/Time
This host  -   Primary
               Active         Ifc Failure              14:23:15 UTC Jun 5 2024
Other host -   Secondary
               Standby Ready  None

====Configuration State===
        Sync Done
====Communication State===
        Mac set
"""

SAMPLE_VERSION_MISMATCH = """\
Failover On
Failover unit Primary
Failover LAN Interface: INTFC GigabitEthernet0/8 (up)
Monitored Interfaces 3 of 110 maximum
Version: Ours 9.20(3)10, Mate 9.18(4)5
Serial Number: Ours JAD251400QT, Mate 9AA77409PDA
Last Failover at: 10:00:00 UTC Jan 1 2025
        This host: Primary - Active
                Active time: 5000 (sec)
                  Interface outside (10.0.0.1): Normal (Monitored)
        Other host: Secondary - Standby Ready
                Active time: 0 (sec)
                  Interface outside (10.0.0.2): Normal (Monitored)
"""

SAMPLE_MATE_FAILED = """\
Failover On
Failover unit Primary
Failover LAN Interface: INTFC GigabitEthernet0/8 (up)
Monitored Interfaces 3 of 110 maximum
Version: Ours 9.20(3)10, Mate 9.20(3)10
Serial Number: Ours JAD251400QT, Mate 9AA77409PDA
Last Failover at: 08:00:00 UTC Dec 1 2024
        This host: Primary - Active
                Active time: 99999 (sec)
                  Interface outside (10.0.0.1): Normal (Monitored)
        Other host: Secondary - Failed
                Active time: 0 (sec)
                  Interface outside (10.0.0.2): Failed (Monitored)
"""

SAMPLE_LAN_DOWN = """\
Failover On
Failover unit Primary
Failover LAN Interface: INTFC GigabitEthernet0/8 (down)
Monitored Interfaces 2 of 110 maximum
Version: Ours 9.20(3)10, Mate 9.20(3)10
Serial Number: Ours JAD251400QT, Mate 9AA77409PDA
Last Failover at: 12:00:00 UTC Mar 15 2025
        This host: Primary - Active
                Active time: 1000 (sec)
                  Interface outside (10.0.0.1): Normal (Monitored)
        Other host: Secondary - Standby Ready
                Active time: 0 (sec)
                  Interface outside (10.0.0.2): Normal (Monitored)
"""

SAMPLE_FAILOVER_OFF = """\
Failover Off
Failover unit Primary
Failover LAN Interface: not Configured
"""

SAMPLE_INTERFACE_FAILED = """\
Failover On
Failover unit Primary
Failover LAN Interface: INTFC GigabitEthernet0/8 (up)
Monitored Interfaces 3 of 110 maximum
Version: Ours 9.20(3)10, Mate 9.20(3)10
Serial Number: Ours JAD251400QT, Mate 9AA77409PDA
Last Failover at: 09:30:00 UTC Feb 20 2025
        This host: Primary - Active
                Active time: 4000 (sec)
                  Interface outside (10.0.0.1): Normal (Monitored)
                  Interface inside (192.168.1.1): Failed (Monitored)
                  Interface management (10.0.1.1): Normal (Monitored)
        Other host: Secondary - Standby Ready
                Active time: 0 (sec)
                  Interface outside (10.0.0.2): Normal (Monitored)
                  Interface inside (192.168.1.2): Normal (Monitored)
                  Interface management (10.0.1.2): Normal (Monitored)
"""

SAMPLE_CONFIG_NOT_SYNCED = """\
               State          Last Failure Reason      Date/Time
This host  -   Primary
               Active         None
Other host -   Secondary
               Standby Ready  None

====Configuration State===
        Sync Skipped - STANDBY
====Communication State===
        Mac set
"""


class TestParseFailoverStatus:
    """Tests for parse_failover_status()."""

    def test_should_parse_healthy_failover(self) -> None:
        status = parse_failover_status(SAMPLE_HEALTHY)
        assert status.failover_enabled is True
        assert status.failover_unit == "Primary"
        assert status.lan_interface_name == "INTFC"
        assert status.lan_hardware == "GigabitEthernet0/8"
        assert status.lan_state == "up"
        assert status.version_ours == "9.20(3)10"
        assert status.version_mate == "9.20(3)10"
        assert status.serial_ours == "JAD251400QT"
        assert status.serial_mate == "9AA77409PDA"
        assert status.monitored_count == 3
        assert status.monitored_max == 110
        assert status.last_failover == "14:23:15 UTC Jun 5 2024"

    def test_should_parse_this_host(self) -> None:
        status = parse_failover_status(SAMPLE_HEALTHY)
        assert status.this_host.role == "Primary"
        assert status.this_host.state == "Active"
        assert status.this_host.active_time == 12345
        assert len(status.this_host.interfaces) == 4

    def test_should_parse_other_host(self) -> None:
        status = parse_failover_status(SAMPLE_HEALTHY)
        assert status.other_host.role == "Secondary"
        assert status.other_host.state == "Standby Ready"
        assert status.other_host.active_time == 0
        assert len(status.other_host.interfaces) == 4

    def test_should_parse_interfaces(self) -> None:
        status = parse_failover_status(SAMPLE_HEALTHY)
        ifaces = status.this_host.interfaces
        assert ifaces[0].name == "outside"
        assert ifaces[0].ip_address == "10.0.0.1"
        assert ifaces[0].status == "Normal"
        assert ifaces[0].monitoring == "Monitored"
        assert ifaces[3].name == "diagnostic"
        assert ifaces[3].monitoring == "Waiting"

    def test_should_parse_config_sync_from_state(self) -> None:
        status = parse_failover_status(SAMPLE_HEALTHY, SAMPLE_FAILOVER_STATE)
        assert status.config_sync_state == "Sync Done"

    def test_should_parse_config_sync_not_synced(self) -> None:
        status = parse_failover_status(SAMPLE_HEALTHY, SAMPLE_CONFIG_NOT_SYNCED)
        assert status.config_sync_state == "Sync Skipped - STANDBY"

    def test_should_detect_version_mismatch(self) -> None:
        status = parse_failover_status(SAMPLE_VERSION_MISMATCH)
        assert status.version_ours == "9.20(3)10"
        assert status.version_mate == "9.18(4)5"

    def test_should_detect_mate_failed(self) -> None:
        status = parse_failover_status(SAMPLE_MATE_FAILED)
        assert status.other_host.state == "Failed"

    def test_should_detect_lan_down(self) -> None:
        status = parse_failover_status(SAMPLE_LAN_DOWN)
        assert status.lan_state == "down"

    def test_should_detect_failover_off(self) -> None:
        status = parse_failover_status(SAMPLE_FAILOVER_OFF)
        assert status.failover_enabled is False
        assert status.failover_unit == "Primary"

    def test_should_detect_failed_interface(self) -> None:
        status = parse_failover_status(SAMPLE_INTERFACE_FAILED)
        inside = status.this_host.interfaces[1]
        assert inside.name == "inside"
        assert inside.status == "Failed"

    def test_should_return_frozen_dataclass(self) -> None:
        status = parse_failover_status(SAMPLE_HEALTHY)
        assert isinstance(status, AsaFailoverStatus)
        try:
            status.failover_enabled = False  # type: ignore[misc,unused-ignore]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass

    def test_should_return_frozen_unit(self) -> None:
        status = parse_failover_status(SAMPLE_HEALTHY)
        assert isinstance(status.this_host, AsaFailoverUnit)
        try:
            status.this_host.state = "changed"  # type: ignore[misc,unused-ignore]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass

    def test_should_return_frozen_interface(self) -> None:
        status = parse_failover_status(SAMPLE_HEALTHY)
        assert isinstance(status.this_host.interfaces[0], AsaFailoverInterface)
        try:
            status.this_host.interfaces[0].status = "changed"  # type: ignore[misc,unused-ignore]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass

    def test_should_handle_empty_string(self) -> None:
        status = parse_failover_status("")
        assert status.failover_enabled is False
        assert status.failover_unit == "unknown"
        assert status.lan_state == "unknown"

    def test_should_default_config_sync_to_unknown(self) -> None:
        status = parse_failover_status(SAMPLE_HEALTHY)
        assert status.config_sync_state == "unknown"

    def test_should_parse_other_host_interfaces_separately(self) -> None:
        status = parse_failover_status(SAMPLE_HEALTHY)
        # Other host interfaces should have different IPs
        other_ifaces = status.other_host.interfaces
        assert other_ifaces[0].ip_address == "10.0.0.2"
        assert other_ifaces[1].ip_address == "192.168.1.2"
