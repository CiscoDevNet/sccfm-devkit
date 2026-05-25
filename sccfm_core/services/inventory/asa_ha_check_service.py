# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from scc_firewall_manager_sdk import (
    AsaInterface,
    ASAInterfacesApi,
    CdoCliResult,
    CdoTransaction,
)

from sccfm_core.factories import ApiClientFactory
from sccfm_core.models.asa_failover_status import (
    AsaFailoverStatus,
    HaCheckResult,
)
from sccfm_core.parsers.asa_failover_parser import parse_failover_status
from sccfm_core.services.inventory.asa_cli_service import AsaCommandLineService
from sccfm_core.types import ConfigLike

_SHOW_FAILOVER = "show failover"
_SHOW_FAILOVER_STATE = "show failover state"
_INTERFACE_PAGE_SIZE = 200


@dataclass(frozen=True)
class UnmonitoredInterface:
    """An enabled interface that is not monitored for failover."""

    hardware_name: str
    name: str


@dataclass(frozen=True)
class AsaHaCheckReport:
    """Complete HA health check report for a single device."""

    failover_status: AsaFailoverStatus
    checks: list[HaCheckResult] = field(default_factory=list)
    unmonitored_interfaces: list[UnmonitoredInterface] = field(default_factory=list)


@dataclass(frozen=True)
class InterfaceLookupResult:
    """Outcome of querying ASA interfaces for HA monitoring coverage."""

    unmonitored_interfaces: list[UnmonitoredInterface] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class AsaHaCheckService:
    """Runs HA health checks on ASA devices via CLI and Interfaces API."""

    def __init__(self, config: ConfigLike) -> None:
        self._cli_service = AsaCommandLineService(config=config)
        self._interfaces_api = ASAInterfacesApi(ApiClientFactory().build(config=config))

    def check_ha(self, device_uids: list[str]) -> dict[str, AsaHaCheckReport] | CdoTransaction:
        """Run HA health checks on the given devices.

        Returns a dict mapping each device UID to its check report,
        or the failed :class:`CdoTransaction` on CLI execution error.
        """
        results: CdoTransaction | list[CdoCliResult] = self._cli_service.execute_cli(
            device_uids=device_uids,
            asa_commands=[_SHOW_FAILOVER, _SHOW_FAILOVER_STATE],
        )
        if isinstance(results, CdoTransaction):
            return results

        parsed = _parse_cli_results(results)
        reports: dict[str, AsaHaCheckReport] = {}

        for device_uid, failover_status in parsed.items():
            interface_lookup = self._find_unmonitored_interfaces(device_uid)
            checks = _run_checks(failover_status, interface_lookup)
            reports[device_uid] = AsaHaCheckReport(
                failover_status=failover_status,
                checks=checks,
                unmonitored_interfaces=interface_lookup.unmonitored_interfaces,
            )

        return reports

    def _find_unmonitored_interfaces(self, device_uid: str) -> InterfaceLookupResult:
        """Query the Interfaces API for enabled interfaces not monitored."""
        physical_lookup = self._query_unmonitored_interfaces(
            device_uid=device_uid,
            fetch_interfaces=self._interfaces_api.get_asa_physical_interfaces,
            scope_name="physical interfaces",
        )
        subinterface_lookup = self._query_unmonitored_interfaces(
            device_uid=device_uid,
            fetch_interfaces=self._interfaces_api.get_asa_sub_interfaces,
            scope_name="subinterfaces",
        )
        return InterfaceLookupResult(
            unmonitored_interfaces=[
                *physical_lookup.unmonitored_interfaces,
                *subinterface_lookup.unmonitored_interfaces,
            ],
            errors=[*physical_lookup.errors, *subinterface_lookup.errors],
        )

    def _query_unmonitored_interfaces(
        self,
        *,
        device_uid: str,
        fetch_interfaces: Callable[..., Any],
        scope_name: str,
    ) -> InterfaceLookupResult:
        offset = 0
        unmonitored_interfaces: list[UnmonitoredInterface] = []

        while True:
            try:
                page = fetch_interfaces(
                    device_uid=device_uid,
                    limit=str(_INTERFACE_PAGE_SIZE),
                    offset=str(offset),
                )
            except Exception as exc:
                return InterfaceLookupResult(
                    unmonitored_interfaces=unmonitored_interfaces,
                    errors=[_format_interface_lookup_error(scope_name, exc)],
                )

            items = list(page.items or [])
            unmonitored_interfaces.extend(_collect_unmonitored_interfaces(items))

            next_offset = _next_interface_offset(
                page=page,
                current_offset=offset,
                page_size=len(items),
            )
            if next_offset is None:
                return InterfaceLookupResult(unmonitored_interfaces=unmonitored_interfaces)
            offset = next_offset


def _is_unmonitored(iface: AsaInterface) -> bool:
    """Return True if the interface is enabled and named but not monitored."""
    if not iface.enabled:
        return False
    if not iface.name:
        return False
    if iface.monitor_interface:
        return False
    return True


def _collect_unmonitored_interfaces(items: list[AsaInterface]) -> list[UnmonitoredInterface]:
    return [
        UnmonitoredInterface(
            hardware_name=iface.hardware_name or "",
            name=iface.name or "",
        )
        for iface in items
        if _is_unmonitored(iface)
    ]


def _next_interface_offset(*, page: Any, current_offset: int, page_size: int) -> int | None:
    if page_size == 0:
        return None

    page_offset = int(page.offset or current_offset)
    next_offset = page_offset + page_size
    total_count = getattr(page, "count", None)

    if total_count is not None and next_offset >= total_count:
        return None
    if page_size < _INTERFACE_PAGE_SIZE:
        return None
    return next_offset


def _parse_cli_results(results: list[CdoCliResult]) -> dict[str, AsaFailoverStatus]:
    """Group CLI results by device and parse combined output."""
    device_outputs: dict[str, dict[str, str]] = {}

    for result in results:
        uid = result.device_uid
        raw = result.result or ""
        commands = _script_commands(result.script or "")

        if uid not in device_outputs:
            device_outputs[uid] = {"show_failover": "", "show_failover_state": ""}

        is_combined = {_SHOW_FAILOVER, _SHOW_FAILOVER_STATE}.issubset(commands)

        if is_combined:
            device_outputs[uid]["show_failover"] = raw
            device_outputs[uid]["show_failover_state"] = raw
        elif _SHOW_FAILOVER_STATE in commands:
            device_outputs[uid]["show_failover_state"] = raw
        else:
            device_outputs[uid]["show_failover"] = raw

    parsed: dict[str, AsaFailoverStatus] = {}
    for uid, outputs in device_outputs.items():
        parsed[uid] = parse_failover_status(
            show_failover_output=outputs["show_failover"],
            show_failover_state_output=outputs["show_failover_state"],
        )

    return parsed


def _script_commands(script: str) -> set[str]:
    return {line.strip().lower() for line in script.splitlines() if line.strip()}


def _run_checks(
    status: AsaFailoverStatus,
    interface_lookup: InterfaceLookupResult,
) -> list[HaCheckResult]:
    """Run all HA health checks against the parsed failover status."""
    checks: list[HaCheckResult] = []
    checks.append(_check_failover_enabled(status))
    checks.append(_check_lan_link(status))
    checks.append(_check_version_match(status))
    checks.append(_check_mate_ready(status))
    checks.append(_check_interfaces_healthy(status))
    checks.append(_check_config_synced(status))
    checks.append(_check_unmonitored(interface_lookup))
    return checks


def _check_failover_enabled(status: AsaFailoverStatus) -> HaCheckResult:
    if status.failover_enabled:
        return HaCheckResult(
            name="failover_enabled",
            passed=True,
            detail="Failover is ON",
        )
    return HaCheckResult(
        name="failover_enabled",
        passed=False,
        detail="Failover is OFF",
    )


def _check_lan_link(status: AsaFailoverStatus) -> HaCheckResult:
    if status.lan_state == "up":
        return HaCheckResult(
            name="lan_link",
            passed=True,
            detail=f"LAN failover link {status.lan_hardware} is up",
        )
    return HaCheckResult(
        name="lan_link",
        passed=False,
        detail=f"LAN failover link {status.lan_hardware} is {status.lan_state}",
    )


def _check_version_match(status: AsaFailoverStatus) -> HaCheckResult:
    if status.version_ours == status.version_mate:
        return HaCheckResult(
            name="version_match",
            passed=True,
            detail=f"Both units running {status.version_ours}",
        )
    return HaCheckResult(
        name="version_match",
        passed=False,
        detail=f"Version mismatch: ours={status.version_ours}, mate={status.version_mate}",
    )


def _check_mate_ready(status: AsaFailoverStatus) -> HaCheckResult:
    this_state = status.this_host.state
    other_state = status.other_host.state

    if (this_state == "Active" and other_state == "Standby Ready") or (
        this_state == "Standby Ready" and other_state == "Active"
    ):
        return HaCheckResult(
            name="mate_ready",
            passed=True,
            detail=f"HA states are healthy: this host is {this_state}, mate is {other_state}",
        )
    return HaCheckResult(
        name="mate_ready",
        passed=False,
        detail=(
            "Unexpected HA states: "
            f"this host is {this_state}, mate is {other_state} "
            "(expected Active/Standby Ready or Standby Ready/Active)"
        ),
    )


def _check_interfaces_healthy(status: AsaFailoverStatus) -> HaCheckResult:
    failed: list[str] = []
    for iface in status.this_host.interfaces:
        if iface.monitoring == "Monitored" and iface.status != "Normal":
            failed.append(f"{iface.name}={iface.status}")
    for iface in status.other_host.interfaces:
        if iface.monitoring == "Monitored" and iface.status != "Normal":
            failed.append(f"{iface.name}(mate)={iface.status}")

    if not failed:
        return HaCheckResult(
            name="interfaces_healthy",
            passed=True,
            detail=f"All {status.monitored_count} monitored interfaces Normal",
        )
    return HaCheckResult(
        name="interfaces_healthy",
        passed=False,
        detail=f"Unhealthy interfaces: {', '.join(failed)}",
    )


def _check_config_synced(status: AsaFailoverStatus) -> HaCheckResult:
    state = status.config_sync_state
    if state.lower().startswith("sync done"):
        return HaCheckResult(
            name="config_synced",
            passed=True,
            detail="Configuration sync completed",
        )
    if state == "unknown":
        return HaCheckResult(
            name="config_synced",
            passed=True,
            detail="Configuration sync state not available (check show failover state)",
        )
    return HaCheckResult(
        name="config_synced",
        passed=False,
        detail=f"Configuration sync: {state}",
    )


def _check_unmonitored(interface_lookup: InterfaceLookupResult) -> HaCheckResult:
    if interface_lookup.errors:
        detail = "Unable to verify interface monitoring via ASA Interfaces API: " + "; ".join(
            interface_lookup.errors
        )
        if interface_lookup.unmonitored_interfaces:
            detail += ". Partial results include: " + ", ".join(
                _format_unmonitored_interface_names(interface_lookup.unmonitored_interfaces)
            )
        return HaCheckResult(
            name="unmonitored_interfaces",
            passed=False,
            detail=detail,
        )

    if not interface_lookup.unmonitored_interfaces:
        return HaCheckResult(
            name="unmonitored_interfaces",
            passed=True,
            detail="All enabled named interfaces are monitored for failover",
        )

    return HaCheckResult(
        name="unmonitored_interfaces",
        passed=False,
        detail=(
            "Enabled interfaces not monitored: "
            + ", ".join(
                _format_unmonitored_interface_names(interface_lookup.unmonitored_interfaces)
            )
        ),
    )


def _format_unmonitored_interface_names(
    unmonitored: list[UnmonitoredInterface],
) -> list[str]:
    return [
        (
            f"{interface.name} ({interface.hardware_name})"
            if interface.hardware_name
            else interface.name
        )
        for interface in unmonitored
    ]


def _format_interface_lookup_error(scope_name: str, exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    return f"{scope_name}: {message}"
