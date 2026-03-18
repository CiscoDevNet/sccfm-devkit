from __future__ import annotations

from typing import List

from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction

from sccfm_core.models.asa_shun_entry import AsaShunEntry, AsaShunInterfaceStats
from sccfm_core.parsers.asa_shun_parser import parse_shun_entries, parse_shun_statistics
from sccfm_core.services.inventory.asa_cli_service import AsaCommandLineService
from sccfm_core.types import ConfigLike

_SHOW_SHUN = "show shun"
_SHOW_SHUN_STATISTICS = "show shun statistics"
_CLEAR_SHUN = "clear shun"


class AsaShunService:
    """Manages shun entries on ASA devices via the CLI service."""

    def __init__(self, config: ConfigLike) -> None:
        self._cli_service = AsaCommandLineService(config=config)

    def view_shun(self, device_uids: List[str]) -> dict[str, List[AsaShunEntry]] | CdoTransaction:
        """Execute ``show shun`` and parse the results.

        Returns a dict mapping each device UID to its parsed shun
        entries, or the failed :class:`CdoTransaction` on error.
        """
        results: CdoTransaction | List[CdoCliResult] = self._cli_service.execute_cli(
            device_uids=device_uids,
            asa_commands=[_SHOW_SHUN],
        )
        if isinstance(results, CdoTransaction):
            return results

        return _parse_shun_entries(results)

    def view_shun_statistics(
        self, device_uids: List[str]
    ) -> dict[str, List[AsaShunInterfaceStats]] | CdoTransaction:
        """Execute ``show shun statistics`` and parse the results.

        Returns a dict mapping each device UID to its parsed
        per-interface statistics, or the failed :class:`CdoTransaction`
        on error.
        """
        results: CdoTransaction | List[CdoCliResult] = self._cli_service.execute_cli(
            device_uids=device_uids,
            asa_commands=[_SHOW_SHUN_STATISTICS],
        )
        if isinstance(results, CdoTransaction):
            return results

        return _parse_shun_stats(results)

    def add_shun(
        self,
        device_uids: List[str],
        source_ip: str,
        dest_ip: str | None = None,
        source_port: int | None = None,
        dest_port: int | None = None,
        protocol: str | None = None,
    ) -> CdoTransaction | List[CdoCliResult]:
        """Execute a ``shun`` command on the given devices.

        When only *source_ip* is provided, all future connections from
        that host are blocked.  The optional connection-tuple parameters
        additionally drop an existing connection immediately.
        """
        cmd = _build_shun_command(
            source_ip=source_ip,
            dest_ip=dest_ip,
            source_port=source_port,
            dest_port=dest_port,
            protocol=protocol,
        )
        return self._cli_service.execute_cli(
            device_uids=device_uids,
            asa_commands=[cmd],
        )

    def remove_shun(
        self, device_uids: List[str], source_ip: str
    ) -> CdoTransaction | List[CdoCliResult]:
        """Execute ``no shun <source_ip>`` on the given devices."""
        return self._cli_service.execute_cli(
            device_uids=device_uids,
            asa_commands=[f"no shun {source_ip}"],
        )

    def clear_shun(self, device_uids: List[str]) -> CdoTransaction | List[CdoCliResult]:
        """Execute ``clear shun`` on the given devices."""
        return self._cli_service.execute_cli(
            device_uids=device_uids,
            asa_commands=[_CLEAR_SHUN],
        )


def _build_shun_command(
    *,
    source_ip: str,
    dest_ip: str | None,
    source_port: int | None,
    dest_port: int | None,
    protocol: str | None,
) -> str:
    """Build a ``shun`` CLI command string from the given parameters."""
    parts = ["shun", source_ip]
    if dest_ip is not None:
        parts.append(dest_ip)
        parts.append(str(source_port or 0))
        parts.append(str(dest_port or 0))
        if protocol is not None:
            parts.append(protocol)
    return " ".join(parts)


def _parse_shun_entries(
    results: List[CdoCliResult],
) -> dict[str, List[AsaShunEntry]]:
    """Parse ``show shun`` results grouped by device."""
    parsed: dict[str, List[AsaShunEntry]] = {}
    for result in results:
        parsed[result.device_uid] = parse_shun_entries(result.result or "")
    return parsed


def _parse_shun_stats(
    results: List[CdoCliResult],
) -> dict[str, List[AsaShunInterfaceStats]]:
    """Parse ``show shun statistics`` results grouped by device."""
    parsed: dict[str, List[AsaShunInterfaceStats]] = {}
    for result in results:
        parsed[result.device_uid] = parse_shun_statistics(result.result or "")
    return parsed
