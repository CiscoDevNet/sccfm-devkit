# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from dataclasses import dataclass

from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction

from cisco_sccfm_core.models.asa_boot_image_change_result import AsaBootImageChangeResult
from cisco_sccfm_core.models.asa_boot_registry import AsaBootRegistry
from cisco_sccfm_core.services.inventory.asa_boot_registry_service import AsaBootRegistryService
from cisco_sccfm_core.services.inventory.asa_cli_service import AsaCommandLineService
from cisco_sccfm_core.types import ConfigLike
from cisco_sccfm_core.utils import validate_asa_image_path, validate_uids

_DIR_COMMAND = "dir {image_path}"
_DIR_DIRECTORY_COMMAND = "dir {directory_path}"
_BOOT_COMMAND = "boot system {image_path}"
_NO_BOOT_COMMAND = "no boot system {image_path}"
_NO_BOOT_ALL_COMMAND = "no boot system"
_WRITE_MEMORY_COMMAND = "write memory"

_DEVICE_ERROR_RE = re.compile(
    r"(?im)(^ERROR:|Command failed|Invalid input|Incomplete command|Ambiguous command)"
)
_IMAGE_NOT_FOUND_RE = re.compile(
    r"(?im)(No such file|Error opening .*\(|Unable to stat|cannot find|not found)"
)
_FILESYSTEM_SUMMARY_RE = re.compile(
    r"(?im)(?P<total>\d+)\s+bytes total\s+\((?P<free>\d+)\s+bytes free[^)]*\)"
)


@dataclass(frozen=True)
class _CliDeviceSummary:
    output: str
    error_messages: list[str]


@dataclass(frozen=True)
class _BootImagePrecheckData:
    current_boot: dict[str, AsaBootRegistry]
    image_summaries: dict[str, _CliDeviceSummary]
    directory_summaries: dict[str, _CliDeviceSummary]
    directory_path: str


@dataclass(frozen=True)
class _FilesystemSummary:
    total_bytes: int
    free_bytes: int


class AsaBootImageService:
    """Checks and changes the configured boot image on ASA devices."""

    def __init__(self, config: ConfigLike) -> None:
        self._cli_service = AsaCommandLineService(config=config)
        self._boot_registry_service = AsaBootRegistryService(config=config)

    def check_boot_image(
        self,
        device_uids: list[str],
        image_path: str,
    ) -> dict[str, AsaBootImageChangeResult] | CdoTransaction:
        validate_uids(device_uids)
        validate_asa_image_path(image_path)

        precheck = self._collect_precheck_data(device_uids=device_uids, image_path=image_path)
        if isinstance(precheck, CdoTransaction):
            return precheck

        results: dict[str, AsaBootImageChangeResult] = {}
        for uid in device_uids:
            results[uid] = self._evaluate_precheck_result(
                device_uid=uid,
                image_path=image_path,
                precheck=precheck,
            )

        return results

    def change_boot_image(
        self,
        device_uids: list[str],
        image_path: str,
    ) -> dict[str, AsaBootImageChangeResult] | CdoTransaction:
        precheck = self.check_boot_image(device_uids=device_uids, image_path=image_path)
        if isinstance(precheck, CdoTransaction):
            return precheck

        results: dict[str, AsaBootImageChangeResult] = {}
        for uid in device_uids:
            current = precheck[uid]
            if current.status != "would_change":
                results[uid] = current
                continue

            changed = self._change_single_device(
                device_uid=uid,
                image_path=image_path,
                boot_system_entries_before=current.boot_system_entries_before,
            )
            if isinstance(changed, CdoTransaction):
                return changed
            results[uid] = changed

        return results

    def _change_single_device(
        self,
        *,
        device_uid: str,
        image_path: str,
        boot_system_entries_before: list[str],
    ) -> AsaBootImageChangeResult | CdoTransaction:
        fallback_image = _derive_fallback_image(boot_system_entries_before, image_path)
        expected_after = _expected_entries_after(image_path, fallback_image)

        attempt_scripts = [
            _build_primary_script(boot_system_entries_before, image_path, fallback_image),
        ]
        if boot_system_entries_before:
            attempt_scripts.append(_build_fallback_script(image_path, fallback_image))

        last_error: str | None = None
        for script in attempt_scripts:
            apply_results = self._cli_service.execute_cli(
                device_uids=[device_uid],
                asa_commands=script,
            )
            if isinstance(apply_results, CdoTransaction):
                return apply_results

            summary = _summarize_cli_results(apply_results).get(device_uid)
            if summary is None:
                last_error = "Did not receive CLI output for boot image update."
                continue

            device_error = _extract_device_error(summary)
            if device_error is not None:
                last_error = device_error
                continue

            verified = self._boot_registry_service.list_boot_registry(device_uids=[device_uid])
            if isinstance(verified, CdoTransaction):
                return verified

            after = verified[device_uid].boot_system_entries
            if after == expected_after:
                return AsaBootImageChangeResult(
                    device_uid=device_uid,
                    requested_image_path=image_path,
                    status="success",
                    message="Boot image changed successfully.",
                    boot_system_entries_before=list(boot_system_entries_before),
                    boot_system_entries_after=list(after),
                )

            return AsaBootImageChangeResult(
                device_uid=device_uid,
                requested_image_path=image_path,
                status="failed",
                message=(
                    "Boot image update did not verify successfully: "
                    f"expected {expected_after} but found {after}."
                ),
                boot_system_entries_before=list(boot_system_entries_before),
                boot_system_entries_after=list(after),
            )

        return AsaBootImageChangeResult(
            device_uid=device_uid,
            requested_image_path=image_path,
            status="failed",
            message=f"Boot image update failed: {last_error or 'unknown device error'}",
            boot_system_entries_before=list(boot_system_entries_before),
            boot_system_entries_after=list(boot_system_entries_before),
        )

    def _collect_precheck_data(
        self,
        *,
        device_uids: list[str],
        image_path: str,
    ) -> _BootImagePrecheckData | CdoTransaction:
        current_boot = self._boot_registry_service.list_boot_registry(device_uids=device_uids)
        if isinstance(current_boot, CdoTransaction):
            return current_boot

        image_results = self._cli_service.execute_cli(
            device_uids=device_uids,
            asa_commands=[_DIR_COMMAND.format(image_path=image_path)],
        )
        if isinstance(image_results, CdoTransaction):
            return image_results

        directory_path = _get_image_directory_path(image_path)
        directory_results = self._cli_service.execute_cli(
            device_uids=device_uids,
            asa_commands=[_DIR_DIRECTORY_COMMAND.format(directory_path=directory_path)],
        )
        if isinstance(directory_results, CdoTransaction):
            return directory_results

        return _BootImagePrecheckData(
            current_boot=current_boot,
            image_summaries=_summarize_cli_results(image_results),
            directory_summaries=_summarize_cli_results(directory_results),
            directory_path=directory_path,
        )

    def _evaluate_precheck_result(
        self,
        *,
        device_uid: str,
        image_path: str,
        precheck: _BootImagePrecheckData,
    ) -> AsaBootImageChangeResult:
        before = _boot_entries_before(precheck.current_boot, device_uid)
        image_summary = precheck.image_summaries.get(device_uid)
        directory_summary = precheck.directory_summaries.get(device_uid)

        if image_summary is None:
            return _build_change_result(
                device_uid=device_uid,
                image_path=image_path,
                status="failed",
                message="Did not receive file validation output for device.",
                before=before,
                after=before,
            )

        directory_error = _validate_directory_summary(
            summary=directory_summary,
            directory_path=precheck.directory_path,
        )
        if directory_error is not None:
            return _build_change_result(
                device_uid=device_uid,
                image_path=image_path,
                status="failed",
                message=directory_error,
                before=before,
                after=before,
            )

        payload = _summary_text(image_summary)
        if _is_image_not_found(payload):
            return _build_change_result(
                device_uid=device_uid,
                image_path=image_path,
                status="image_not_found",
                message=_build_precheck_message(
                    base_message=f"Image path '{image_path}' was not found on device.",
                    directory_summary=directory_summary,
                    directory_path=precheck.directory_path,
                ),
                before=before,
                after=before,
            )

        device_error = _extract_device_error(image_summary)
        if device_error is not None:
            return _build_change_result(
                device_uid=device_uid,
                image_path=image_path,
                status="failed",
                message=f"Image validation failed: {device_error}",
                before=before,
                after=before,
            )

        if not image_summary.output.strip():
            return _build_change_result(
                device_uid=device_uid,
                image_path=image_path,
                status="failed",
                message="Image validation returned no output for device.",
                before=before,
                after=before,
            )

        fallback_image = _derive_fallback_image(before, image_path)
        expected_after = _expected_entries_after(image_path, fallback_image)

        if before == expected_after:
            return _build_change_result(
                device_uid=device_uid,
                image_path=image_path,
                status="no_change",
                message=_build_precheck_message(
                    base_message="Requested image is already the configured primary boot image.",
                    directory_summary=directory_summary,
                    directory_path=precheck.directory_path,
                ),
                before=before,
                after=before,
            )

        return _build_change_result(
            device_uid=device_uid,
            image_path=image_path,
            status="would_change",
            message=_build_precheck_message(
                base_message="Boot image would be changed to the requested image.",
                directory_summary=directory_summary,
                directory_path=precheck.directory_path,
            ),
            before=before,
            after=expected_after,
        )


def _derive_fallback_image(current_entries: list[str], image_path: str) -> str | None:
    """Return the previous primary image to keep as fallback, or None."""
    if not current_entries:
        return None
    old_primary = current_entries[0]
    if old_primary == image_path:
        return None
    return old_primary


def _expected_entries_after(image_path: str, fallback_image: str | None) -> list[str]:
    """Return the boot entry list we expect after a successful change."""
    if fallback_image is None:
        return [image_path]
    return [image_path, fallback_image]


def _build_primary_script(
    current_entries: list[str], image_path: str, fallback_image: str | None
) -> list[str]:
    # This mirrors what a network engineer would do manually and what Cisco TAC
    # recommends: set the requested image as primary and keep the previous primary
    # as the sole fallback.
    #
    # We clear all existing entries and write at most two:
    #   1. The new requested image (primary)
    #   2. The previous primary image (fallback), only when it differs from the new one
    #
    # Why exactly two entries:
    # - The ASA allows up to 4 boot system entries, but stale entries pointing to
    #   very old images risk booting into a version incompatible with the current
    #   running config (removed features, syntax changes, etc.).
    # - The previous primary is the only fallback we can trust — it was *just*
    #   running successfully with the current config.
    # - Keeping only 2 entries leaves free slots for manual maintenance-window
    #   overrides without requiring cleanup first.
    if not current_entries:
        return [_BOOT_COMMAND.format(image_path=image_path), _WRITE_MEMORY_COMMAND]

    commands: list[str] = [_NO_BOOT_COMMAND.format(image_path=entry) for entry in current_entries]
    commands.append(_BOOT_COMMAND.format(image_path=image_path))
    if fallback_image is not None:
        commands.append(_BOOT_COMMAND.format(image_path=fallback_image))
    commands.append(_WRITE_MEMORY_COMMAND)
    return commands


def _build_fallback_script(image_path: str, fallback_image: str | None) -> list[str]:
    commands: list[str] = [
        _NO_BOOT_ALL_COMMAND,
        _BOOT_COMMAND.format(image_path=image_path),
    ]
    if fallback_image is not None:
        commands.append(_BOOT_COMMAND.format(image_path=fallback_image))
    commands.append(_WRITE_MEMORY_COMMAND)
    return commands


def _summarize_cli_results(results: list[CdoCliResult]) -> dict[str, _CliDeviceSummary]:
    grouped: dict[str, dict[str, list[str]]] = {}
    for result in results:
        bucket = grouped.setdefault(result.device_uid, {"output": [], "error_messages": []})
        if result.result:
            bucket["output"].append(result.result)
        if result.error_msg:
            bucket["error_messages"].append(result.error_msg)

    return {
        uid: _CliDeviceSummary(
            output="\n".join(parts["output"]).strip(),
            error_messages=list(parts["error_messages"]),
        )
        for uid, parts in grouped.items()
    }


def _summary_text(summary: _CliDeviceSummary) -> str:
    parts = [summary.output, *summary.error_messages]
    return "\n".join([part for part in parts if part]).strip()


def _boot_entries_before(
    current_boot: dict[str, AsaBootRegistry],
    device_uid: str,
) -> list[str]:
    if device_uid not in current_boot:
        return []
    return list(current_boot[device_uid].boot_system_entries)


def _build_change_result(
    *,
    device_uid: str,
    image_path: str,
    status: str,
    message: str,
    before: list[str],
    after: list[str],
) -> AsaBootImageChangeResult:
    return AsaBootImageChangeResult(
        device_uid=device_uid,
        requested_image_path=image_path,
        status=status,
        message=message,
        boot_system_entries_before=list(before),
        boot_system_entries_after=list(after),
    )


def _is_image_not_found(text: str) -> bool:
    return bool(text and _IMAGE_NOT_FOUND_RE.search(text))


def _get_image_directory_path(image_path: str) -> str:
    filesystem, _, remainder = image_path.partition(":/")
    directory, _, _filename = remainder.rpartition("/")
    if not directory:
        return f"{filesystem}:/"
    return f"{filesystem}:/{directory}"


def _validate_directory_summary(
    summary: _CliDeviceSummary | None, directory_path: str
) -> str | None:
    if summary is None:
        return "Did not receive filesystem inspection output for device."

    device_error = _extract_device_error(summary)
    if device_error is not None:
        return f"Filesystem inspection failed for '{directory_path}': {device_error}"

    if not summary.output.strip():
        return f"Filesystem inspection returned no output for '{directory_path}'."

    return None


def _build_precheck_message(
    *,
    base_message: str,
    directory_summary: _CliDeviceSummary | None,
    directory_path: str,
) -> str:
    detail = _describe_directory_summary(directory_summary, directory_path)
    return f"{base_message} {detail}".strip() if detail else base_message


def _describe_directory_summary(
    summary: _CliDeviceSummary | None,
    directory_path: str,
) -> str:
    if summary is None:
        return ""

    filesystem = _parse_filesystem_summary(summary.output)
    if filesystem is None:
        return (
            f"Containing directory '{directory_path}' was inspected, but the device output "
            "did not include a parseable free-space summary."
        )

    return (
        f"Containing directory '{directory_path}' reports {filesystem.free_bytes} bytes free "
        f"out of {filesystem.total_bytes} total."
    )


def _parse_filesystem_summary(output: str) -> _FilesystemSummary | None:
    match = _FILESYSTEM_SUMMARY_RE.search(output)
    if match is None:
        return None

    return _FilesystemSummary(
        total_bytes=int(match.group("total")),
        free_bytes=int(match.group("free")),
    )


def _extract_device_error(summary: _CliDeviceSummary) -> str | None:
    if summary.error_messages:
        return " ".join(summary.error_messages)

    match = _DEVICE_ERROR_RE.search(summary.output)
    if not match:
        return None

    lines = [line.strip() for line in summary.output.splitlines() if line.strip()]
    return " ".join(lines)
