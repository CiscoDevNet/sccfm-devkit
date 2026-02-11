from __future__ import annotations

from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction

from sccfm_core.models.asa_disk_file import AsaDiskFile
from sccfm_core.parsers.asa_disk_file_parser import parse_disk_file_listing
from sccfm_core.services.inventory.asa_cli_service import AsaCommandLineService
from sccfm_core.types import ConfigLike

_DIR_COMMAND = "dir disk0:"


class AsaDiskFileService:
    """Lists OS and AnyConnect files on ASA device disks."""

    def __init__(self, config: ConfigLike) -> None:
        self._cli_service = AsaCommandLineService(config=config)

    def list_disk_files(
        self, device_uids: list[str]
    ) -> dict[str, list[AsaDiskFile]] | CdoTransaction:
        """Execute ``dir disk0:`` on the given devices and parse the results.

        Returns a dict mapping each device UID to its parsed file list.
        If the CLI execution fails, returns the failed
        :class:`CdoTransaction` instead.
        """
        results: CdoTransaction | list[CdoCliResult] = self._cli_service.execute_cli(
            device_uids=device_uids,
            asa_commands=[_DIR_COMMAND],
        )
        if isinstance(results, CdoTransaction):
            return results

        return _parse_results(results)


def _parse_results(results: list[CdoCliResult]) -> dict[str, list[AsaDiskFile]]:
    """Parse CLI results into a device-uid-keyed dict of disk files."""
    parsed: dict[str, list[AsaDiskFile]] = {}
    for result in results:
        raw_output = result.result or ""
        parsed[result.device_uid] = parse_disk_file_listing(raw_output)
    return parsed
