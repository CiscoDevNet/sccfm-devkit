from __future__ import annotations

from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction

from sccfm_core.models.asa_boot_registry import AsaBootRegistry
from sccfm_core.parsers.asa_boot_registry_parser import parse_boot_registry
from sccfm_core.services.inventory.asa_cli_service import AsaCommandLineService
from sccfm_core.types import ConfigLike

_SHOW_VERSION = "show version"
_SHOW_RUN_BOOT = "show run boot"


class AsaBootRegistryService:
    """Retrieves and parses boot registry info from ASA devices."""

    def __init__(self, config: ConfigLike) -> None:
        self._cli_service = AsaCommandLineService(config=config)

    def list_boot_registry(
        self, device_uids: list[str]
    ) -> dict[str, AsaBootRegistry] | CdoTransaction:
        """Execute ``show version`` and ``show run boot`` on the given
        devices, then parse the results into :class:`AsaBootRegistry`
        objects.

        Returns a dict mapping each device UID to its parsed boot
        registry.  If the CLI execution fails, returns the failed
        :class:`CdoTransaction` instead.
        """
        results: CdoTransaction | list[CdoCliResult] = self._cli_service.execute_cli(
            device_uids=device_uids,
            asa_commands=[_SHOW_VERSION, _SHOW_RUN_BOOT],
        )
        if isinstance(results, CdoTransaction):
            return results

        return _parse_results(results)


def _parse_results(
    results: list[CdoCliResult],
) -> dict[str, AsaBootRegistry]:
    """Group CLI results by device and parse combined output.

    The SDK may return results in two forms:

    1. **One result per command** — each ``CdoCliResult`` has a single
       command in ``script`` and only that command's output in
       ``result``.
    2. **Combined result** — a single ``CdoCliResult`` whose ``script``
       contains both commands (newline-separated) and whose ``result``
       holds the concatenated output.

    This function handles both forms transparently.
    """
    device_outputs: dict[str, dict[str, str]] = {}

    for result in results:
        uid = result.device_uid
        raw = result.result or ""
        script = (result.script or "").strip().lower()

        if uid not in device_outputs:
            device_outputs[uid] = {"show_version": "", "show_run_boot": ""}

        is_combined = "show version" in script and "show run" in script

        if is_combined:
            # SDK returned concatenated output — the parser's regexes
            # will each extract the fields they need from the full text.
            device_outputs[uid]["show_version"] = raw
            device_outputs[uid]["show_run_boot"] = raw
        elif "show run" in script:
            device_outputs[uid]["show_run_boot"] = raw
        else:
            device_outputs[uid]["show_version"] = raw

    parsed: dict[str, AsaBootRegistry] = {}
    for uid, outputs in device_outputs.items():
        parsed[uid] = parse_boot_registry(
            show_version_output=outputs["show_version"],
            show_run_boot_output=outputs["show_run_boot"],
        )
    return parsed
