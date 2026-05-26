# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re

from scc_firewall_manager_sdk import CdoCliResult, CdoTransaction

from sccfm_core.models.asa_local_user import AsaLocalUser
from sccfm_core.models.asa_password_change_result import AsaPasswordChangeResult
from sccfm_core.parsers.asa_local_user_parser import parse_local_user
from sccfm_core.services.inventory.asa_cli_service import AsaCommandLineService
from sccfm_core.types import ConfigLike

_ERROR_RE = re.compile(r"(?i)^ERROR:|Command failed", re.MULTILINE)


def _show_username_command(username: str) -> str:
    return f"show running-config username {username}"


def _set_password_command(username: str, password: str) -> str:
    return f"username {username} password {password}"


class AsaUserPasswordService:
    """Changes a local user password on ASA devices with verification.

    The SCCFM API redacts password hashes in CLI output (they appear as
    ``*****``), so hash-based verification is not possible.  Instead the
    service verifies by checking that the change command produced no
    device-level errors and the user is still present in the running
    config afterward.

    If the ASA rejects the password (e.g. policy violation), the device
    keeps the original password unchanged — no rollback is needed.
    """

    def __init__(self, config: ConfigLike) -> None:
        self._cli_service = AsaCommandLineService(config=config)

    def change_password(
        self,
        device_uids: list[str],
        username: str,
        new_password: str,
    ) -> dict[str, AsaPasswordChangeResult] | CdoTransaction:
        """Change a local user password on the given ASA devices.

        1. **Pre-check** -- verify the user exists on each device.
        2. **Apply** -- send the ``username ... password`` command.
        3. **Verify** -- re-read the config to confirm the user is intact.

        Returns a dict mapping each device UID to its
        :class:`AsaPasswordChangeResult`, or a failed
        :class:`CdoTransaction` if the CLI call fails entirely.
        """
        existing_users = self._check_user_exists(device_uids, username)
        if isinstance(existing_users, CdoTransaction):
            return existing_users

        eligible_uids, results = self._partition_eligible(device_uids, existing_users, username)
        if not eligible_uids:
            return results

        apply_outcome = self._apply_password(eligible_uids, username, new_password)
        if isinstance(apply_outcome, CdoTransaction):
            return apply_outcome

        verify_outcome = self._verify_change(eligible_uids, username)
        if isinstance(verify_outcome, CdoTransaction):
            return verify_outcome

        changed = self._build_results(apply_outcome, verify_outcome, eligible_uids, username)
        results.update(changed)

        return results

    # ------------------------------------------------------------------
    # Phases
    # ------------------------------------------------------------------

    def _check_user_exists(
        self,
        device_uids: list[str],
        username: str,
    ) -> dict[str, AsaLocalUser | None] | CdoTransaction:
        """Phase 1: confirm the user exists on each device."""
        results = self._cli_service.execute_cli(
            device_uids=device_uids,
            asa_commands=[_show_username_command(username)],
        )
        if isinstance(results, CdoTransaction):
            return results
        return _parse_users(results)

    def _apply_password(
        self,
        device_uids: list[str],
        username: str,
        new_password: str,
    ) -> dict[str, str | None] | CdoTransaction:
        """Phase 2: send the password change command.

        Returns a dict mapping device UID to the raw CLI output (which
        may contain device-level errors like password policy violations).
        """
        results = self._cli_service.execute_cli(
            device_uids=device_uids,
            asa_commands=[_set_password_command(username, new_password)],
        )
        if isinstance(results, CdoTransaction):
            return results
        return {r.device_uid: r.result for r in results}

    def _verify_change(
        self,
        device_uids: list[str],
        username: str,
    ) -> dict[str, AsaLocalUser | None] | CdoTransaction:
        """Phase 3: re-read the user config to confirm user is still present."""
        results = self._cli_service.execute_cli(
            device_uids=device_uids,
            asa_commands=[_show_username_command(username)],
        )
        if isinstance(results, CdoTransaction):
            return results
        return _parse_users(results)

    def _build_results(
        self,
        apply_outputs: dict[str, str | None],
        post_change_users: dict[str, AsaLocalUser | None],
        device_uids: list[str],
        username: str,
    ) -> dict[str, AsaPasswordChangeResult]:
        """Evaluate results using both the change output and verification."""
        results: dict[str, AsaPasswordChangeResult] = {}
        for uid in device_uids:
            raw_output = apply_outputs.get(uid) or ""
            device_error = _extract_device_error(raw_output)

            if device_error:
                results[uid] = AsaPasswordChangeResult(
                    device_uid=uid,
                    status="failed",
                    message=f"Device rejected password change: {device_error}",
                )
                continue

            user_after = post_change_users.get(uid)
            if user_after is None:
                results[uid] = AsaPasswordChangeResult(
                    device_uid=uid,
                    status="failed",
                    message="Could not read back user config after password change.",
                )
            else:
                results[uid] = AsaPasswordChangeResult(
                    device_uid=uid,
                    status="success",
                    message="Password changed successfully.",
                )
        return results

    @staticmethod
    def _partition_eligible(
        device_uids: list[str],
        existing_users: dict[str, AsaLocalUser | None],
        username: str,
    ) -> tuple[list[str], dict[str, AsaPasswordChangeResult]]:
        """Split devices into eligible (user exists) and not-found results."""
        eligible: list[str] = []
        results: dict[str, AsaPasswordChangeResult] = {}
        for uid in device_uids:
            if existing_users.get(uid) is not None:
                eligible.append(uid)
            else:
                results[uid] = AsaPasswordChangeResult(
                    device_uid=uid,
                    status="user_not_found",
                    message=f"User '{username}' not found on device.",
                )
        return eligible, results


def _parse_users(
    results: list[CdoCliResult],
) -> dict[str, AsaLocalUser | None]:
    """Parse CLI results into a device-uid-keyed dict of local users."""
    parsed: dict[str, AsaLocalUser | None] = {}
    for result in results:
        raw_output = result.result or ""
        parsed[result.device_uid] = parse_local_user(raw_output)
    return parsed


def _extract_device_error(raw_output: str) -> str | None:
    """Return a cleaned error message if the output contains device-level errors."""
    if not _ERROR_RE.search(raw_output):
        return None
    lines = [line.strip() for line in raw_output.strip().splitlines() if line.strip()]
    return " ".join(lines)
