# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Reset the dedicated FTD registration fixture to an unmanaged state."""

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
    """Delete the fixture's manager after validating an exact-host safety guard."""
    host = os.getenv("FTD_HOST", "").strip()
    if not host:
        return False

    allowed_host = os.getenv(_ALLOWED_HOST_ENV, "").strip()
    if not allowed_host or host != allowed_host:
        raise FtdManagerCleanupError(
            f"Refusing FTD manager cleanup for {host!r}; {_ALLOWED_HOST_ENV} must match exactly."
        )

    password = os.getenv("SCCFM_FTD_PASSWORD", "")
    if not password:
        raise FtdManagerCleanupError("SCCFM_FTD_PASSWORD is required for FTD manager cleanup.")

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

    raise FtdManagerCleanupError(
        f"Could not remove the manager from FTD {host} after {retries} attempts."
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
