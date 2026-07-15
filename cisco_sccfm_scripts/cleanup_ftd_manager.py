# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Reset the dedicated FTD registration fixture to an unmanaged state.

Both e2e suites (CLI and Ansible) share one persistent FTD VM.  The
``configure_manager`` test registers it against the cdFMC; this module removes
that registration over SSH (``configure manager delete``) so each suite starts
and ends with a clean device.  It is invoked four times per pipeline: before and
after the CLI suite, and before and after the Ansible suite.

Deleting a manager is destructive, so cleanup is refused unless
``SCCFM_E2E_FTD_MANAGER_DELETE_HOST`` matches ``FTD_HOST`` exactly.  CI sets both
to the reserved fixture (10.10.3.101); a developer who only exports ``FTD_HOST``
cannot accidentally wipe an arbitrary appliance.
"""

from __future__ import annotations

import os
import sys
import time

from cisco_sccfm_core.services.inventory import (
    FtdConfigureManagerError,
    FtdConfigureManagerService,
    JumpHostSpec,
    parse_jump_host,
)

_ALLOWED_HOST_ENV = "SCCFM_E2E_FTD_MANAGER_DELETE_HOST"


class FtdManagerCleanupError(RuntimeError):
    """Raised when guarded E2E manager cleanup cannot complete safely."""


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "")
    try:
        parsed = int(value) if value else default
    except ValueError as exc:
        raise FtdManagerCleanupError(f"{name} must be an integer.") from exc
    if parsed < 1:
        raise FtdManagerCleanupError(f"{name} must be at least 1.")
    return parsed


def _jump_host() -> JumpHostSpec | None:
    value = os.getenv("FTD_JUMP_HOST", "").strip()
    if not value:
        return None
    try:
        return parse_jump_host(value, os.getenv("SCCFM_JUMP_PASSWORD") or None)
    except ValueError as exc:
        raise FtdManagerCleanupError(str(exc)) from exc


def cleanup_manager_from_environment() -> bool:
    """Delete the fixture's manager after validating an exact-host safety guard.

    Returns ``True`` when a cleanup ran, ``False`` when the registration E2E is
    not configured (so there is nothing to reset). Raises
    :class:`FtdManagerCleanupError` only when cleanup is actually requested but
    the inputs are unsafe, or the SSH delete never confirms.

    The opt-in signal is the delete-host guard plus the SSH password, NOT
    ``FTD_HOST`` alone: Jenkins exposes every build parameter as an env var, so
    ``FTD_HOST`` carries its default even on ASA-only runs. Treat a missing
    guard/password as "not requested" and skip; only a guard that is set but
    mismatched is an error.
    """
    host = os.getenv("FTD_HOST", "").strip()
    allowed_host = os.getenv(_ALLOWED_HOST_ENV, "").strip()
    password = os.getenv("SCCFM_FTD_PASSWORD", "")

    # Not requested: the caller did not opt into FTD registration this run.
    if not host or not allowed_host or not password:
        return False

    if host != allowed_host:
        raise FtdManagerCleanupError(
            f"Refusing FTD manager cleanup for {host!r}; {_ALLOWED_HOST_ENV} must match exactly."
        )

    port = _env_int("FTD_PORT", 22)
    if port > 65535:
        raise FtdManagerCleanupError("FTD_PORT must not exceed 65535.")
    timeout = _env_int("FTD_SSH_TIMEOUT", 60)
    retries = _env_int("FTD_MANAGER_CLEANUP_RETRIES", 3)
    delay = _env_int("FTD_MANAGER_CLEANUP_DELAY", 10)
    username = os.getenv("FTD_USER", "admin").strip() or "admin"
    jump = _jump_host()
    service = FtdConfigureManagerService()

    last_error: FtdConfigureManagerError | None = None
    for attempt in range(1, retries + 1):
        try:
            service.delete_manager(
                host=host,
                port=port,
                username=username,
                password=password,
                timeout=timeout,
                jump=jump,
            )
            return True
        except FtdConfigureManagerError as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(delay)

    detail = str(last_error) if last_error is not None else "unknown SSH error"
    if last_error is not None and last_error.output:
        detail = f"{detail}\nDevice output:\n{last_error.output}"
    raise FtdManagerCleanupError(
        f"Could not remove the manager from FTD {host} after {retries} attempts: {detail}"
    ) from last_error


def main() -> int:
    try:
        cleaned = cleanup_manager_from_environment()
    except FtdManagerCleanupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if cleaned:
        print("Persistent FTD manager cleanup completed.")
    else:
        print("FTD_HOST is unset; skipping persistent FTD manager cleanup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
