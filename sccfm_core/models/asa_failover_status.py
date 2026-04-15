from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AsaFailoverInterface:
    """A single interface entry from ``show failover`` output.

    Example::

        Interface outside (10.0.0.1): Normal (Monitored)
    """

    name: str
    ip_address: str
    status: str
    monitoring: str


@dataclass(frozen=True)
class AsaFailoverUnit:
    """One unit (This host / Other host) from ``show failover`` output."""

    role: str
    state: str
    active_time: int
    interfaces: list[AsaFailoverInterface] = field(default_factory=list)


@dataclass(frozen=True)
class AsaFailoverStatus:
    """Parsed representation of ``show failover`` and ``show failover state``."""

    failover_enabled: bool
    failover_unit: str
    lan_interface_name: str
    lan_hardware: str
    lan_state: str
    version_ours: str
    version_mate: str
    serial_ours: str
    serial_mate: str
    last_failover: str
    monitored_count: int
    monitored_max: int
    this_host: AsaFailoverUnit
    other_host: AsaFailoverUnit
    config_sync_state: str


@dataclass(frozen=True)
class HaCheckResult:
    """Result of a single HA health check."""

    name: str
    passed: bool
    detail: str
